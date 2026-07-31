//! Normalized-path transaction coordinator for persistence adapters.
//!
//! Each file path has one exclusive async transaction and at most one active
//! operation per logical key. Concurrent callers share the typed success
//! result; selected semantic outcomes can remain visible until the owning
//! adapter explicitly forgets them after a successful replacement write.

use std::collections::HashMap;
use std::env;
use std::future::Future;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex as StdMutex, OnceLock};

use tokio::sync::{watch, Mutex as AsyncMutex};

struct ActiveFlight<K, T> {
    id: u64,
    key: K,
    receiver: watch::Receiver<Option<Arc<T>>>,
}

struct FlightState<K, T> {
    next_id: u64,
    active: Option<ActiveFlight<K, T>>,
    remembered: Option<(K, T)>,
}

struct PathTransaction<K, T> {
    exclusive: AsyncMutex<()>,
    flight: StdMutex<FlightState<K, T>>,
}

struct FlightCleanup<'a, K, T> {
    owner: &'a PathTransaction<K, T>,
    id: u64,
    armed: bool,
}

impl<K, T> Drop for FlightCleanup<'_, K, T> {
    fn drop(&mut self) {
        if !self.armed {
            return;
        }
        let mut state = self
            .owner
            .flight
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        if state
            .active
            .as_ref()
            .is_some_and(|active| active.id == self.id)
        {
            state.active = None;
        }
    }
}

impl<K, T> PathTransaction<K, T>
where
    K: Clone + Eq,
    T: Clone,
{
    fn new() -> Self {
        Self {
            exclusive: AsyncMutex::new(()),
            flight: StdMutex::new(FlightState {
                next_id: 0,
                active: None,
                remembered: None,
            }),
        }
    }

    async fn run_single_flight<F, Fut, E, P>(
        &self,
        key: K,
        remember: P,
        operation: F,
    ) -> Result<T, E>
    where
        F: FnOnce() -> Fut,
        Fut: Future<Output = Result<T, E>>,
        P: Fn(&T) -> bool,
    {
        let mut operation = Some(operation);
        loop {
            let role = {
                let mut state = self
                    .flight
                    .lock()
                    .unwrap_or_else(|poisoned| poisoned.into_inner());
                if let Some((remembered_key, value)) = &state.remembered {
                    if remembered_key == &key {
                        FlightRole::Return(value.clone())
                    } else if let Some(active) = &state.active {
                        flight_role(active, &key)
                    } else {
                        lead_flight(&mut state, key.clone())
                    }
                } else if let Some(active) = &state.active {
                    flight_role(active, &key)
                } else {
                    lead_flight(&mut state, key.clone())
                }
            };

            match role {
                FlightRole::Return(value) => return Ok(value),
                FlightRole::Join(receiver) => {
                    if let Some(value) = shared_flight_value(receiver).await {
                        return Ok(value);
                    }
                }
                FlightRole::Wait(receiver) => {
                    let _ = shared_flight_value(receiver).await;
                }
                FlightRole::Lead { id, sender } => {
                    let mut cleanup = FlightCleanup {
                        owner: self,
                        id,
                        armed: true,
                    };
                    // Give callers released by the same scheduling event a
                    // chance to subscribe before a fast filesystem read ends.
                    tokio::task::yield_now().await;
                    let exclusive = self.exclusive.lock().await;
                    let result = operation.take().expect("single-flight leader operation")().await;
                    if let Ok(value) = &result {
                        sender.send_replace(Some(Arc::new(value.clone())));
                    }
                    let mut state = self
                        .flight
                        .lock()
                        .unwrap_or_else(|poisoned| poisoned.into_inner());
                    if state.active.as_ref().is_some_and(|active| active.id == id) {
                        state.active = None;
                    }
                    if let Ok(value) = &result {
                        if remember(value) {
                            state.remembered = Some((key.clone(), value.clone()));
                        }
                    }
                    cleanup.armed = false;
                    drop(state);
                    drop(exclusive);
                    drop(sender);
                    return result;
                }
            }
        }
    }
}

fn flight_role<K, T>(active: &ActiveFlight<K, T>, key: &K) -> FlightRole<T>
where
    K: Eq,
{
    if &active.key == key {
        FlightRole::Join(active.receiver.clone())
    } else {
        FlightRole::Wait(active.receiver.clone())
    }
}

fn lead_flight<K, T>(state: &mut FlightState<K, T>, key: K) -> FlightRole<T> {
    let id = state.next_id;
    state.next_id = state.next_id.wrapping_add(1);
    let (sender, receiver) = watch::channel(None);
    state.active = Some(ActiveFlight { id, key, receiver });
    FlightRole::Lead { id, sender }
}

enum FlightRole<T> {
    Lead {
        id: u64,
        sender: watch::Sender<Option<Arc<T>>>,
    },
    Return(T),
    Join(watch::Receiver<Option<Arc<T>>>),
    Wait(watch::Receiver<Option<Arc<T>>>),
}

async fn shared_flight_value<T: Clone>(mut receiver: watch::Receiver<Option<Arc<T>>>) -> Option<T> {
    if let Some(value) = receiver.borrow().as_ref() {
        return Some((**value).clone());
    }
    if receiver.changed().await.is_err() {
        return None;
    }
    let value = receiver.borrow().clone()?;
    Some((*value).clone())
}

type TransactionRegistry<K, T> = StdMutex<HashMap<PathBuf, Arc<PathTransaction<K, T>>>>;

pub(super) struct PathTransactions<K, T> {
    registry: OnceLock<TransactionRegistry<K, T>>,
}

impl<K, T> PathTransactions<K, T>
where
    K: Clone + Eq,
    T: Clone,
{
    pub(super) const fn new() -> Self {
        Self {
            registry: OnceLock::new(),
        }
    }

    pub(super) async fn run<F, Fut, E>(&self, path: &Path, key: K, operation: F) -> Result<T, E>
    where
        F: FnOnce() -> Fut,
        Fut: Future<Output = Result<T, E>>,
    {
        self.coordinator(path)
            .run_single_flight(key, |_| false, operation)
            .await
    }

    pub(super) async fn run_remembering<F, Fut, E, P>(
        &self,
        path: &Path,
        key: K,
        remember: P,
        operation: F,
    ) -> Result<T, E>
    where
        F: FnOnce() -> Fut,
        Fut: Future<Output = Result<T, E>>,
        P: Fn(&T) -> bool,
    {
        self.coordinator(path)
            .run_single_flight(key, remember, operation)
            .await
    }

    pub(super) async fn exclusive<F, Fut, R>(&self, path: &Path, operation: F) -> R
    where
        F: FnOnce() -> Fut,
        Fut: Future<Output = R>,
    {
        let coordinator = self.coordinator(path);
        let _exclusive = coordinator.exclusive.lock().await;
        operation().await
    }

    pub(super) fn clear_remembered(&self, path: &Path) {
        let coordinator = self.coordinator(path);
        let mut state = coordinator
            .flight
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        state.remembered = None;
    }

    fn coordinator(&self, path: &Path) -> Arc<PathTransaction<K, T>> {
        let key = normalized_path(path);
        let registry = self.registry.get_or_init(|| StdMutex::new(HashMap::new()));
        let mut registry = registry
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        if let Some(transaction) = registry.get(&key) {
            Arc::clone(transaction)
        } else {
            let transaction = Arc::new(PathTransaction::new());
            registry.insert(key, Arc::clone(&transaction));
            transaction
        }
    }
}

fn normalized_path(path: &Path) -> PathBuf {
    if let Ok(canonical) = std::fs::canonicalize(path) {
        return canonical;
    }

    let absolute = if path.is_absolute() {
        path.to_path_buf()
    } else {
        env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join(path)
    };
    match (absolute.parent(), absolute.file_name()) {
        (Some(parent), Some(file_name)) => std::fs::canonicalize(parent)
            .map(|canonical_parent| canonical_parent.join(file_name))
            .unwrap_or(absolute),
        _ => absolute,
    }
}

#[cfg(test)]
mod tests {
    use super::PathTransactions;
    use std::future::pending;
    use std::path::PathBuf;
    use std::sync::Arc;
    use std::time::Duration;
    use tokio::sync::Notify;
    use tokio::time::timeout;

    #[tokio::test]
    async fn cancelled_leader_releases_the_path_flight() {
        let transactions = Arc::new(PathTransactions::<u8, u8>::new());
        let path = PathBuf::from("cancelled-single-flight.json");
        let started = Arc::new(Notify::new());
        let started_wait = started.notified();
        let leader_started = Arc::clone(&started);
        let leader_transactions = Arc::clone(&transactions);
        let leader_path = path.clone();
        let leader = tokio::spawn(async move {
            leader_transactions
                .run(&leader_path, 1, || async move {
                    leader_started.notify_one();
                    pending::<Result<u8, ()>>().await
                })
                .await
        });
        started_wait.await;
        leader.abort();
        let _ = leader.await;

        let result = timeout(
            Duration::from_secs(1),
            transactions.run(&path, 1, || async { Ok::<u8, ()>(2) }),
        )
        .await
        .expect("replacement flight must not hang")
        .expect("replacement flight succeeds");
        assert_eq!(result, 2);
    }
}
