//! Shared bounded UTF-8 NDJSON input primitives for backend child processes.

use std::io;

use tokio::io::{AsyncBufRead, AsyncBufReadExt, AsyncRead, BufReader};

struct NdjsonLine {
    text: String,
    raw_byte_count: usize,
    terminated: bool,
}

async fn read_line_record<R: AsyncBufRead + Unpin>(
    reader: &mut R,
    line_limit: usize,
) -> io::Result<Option<NdjsonLine>> {
    let mut bytes = Vec::new();
    loop {
        let available = reader.fill_buf().await?;
        if available.is_empty() {
            if bytes.is_empty() {
                return Ok(None);
            }
            break;
        }
        let end = available
            .iter()
            .position(|byte| *byte == b'\n')
            .map_or(available.len(), |index| index + 1);
        if bytes.len().saturating_add(end) > line_limit {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!("backend output line exceeded the {line_limit}-byte contract limit"),
            ));
        }
        bytes.extend_from_slice(&available[..end]);
        reader.consume(end);
        if bytes.last() == Some(&b'\n') {
            break;
        }
    }

    let raw_byte_count = bytes.len();
    let terminated = bytes.last() == Some(&b'\n');
    if terminated {
        bytes.pop();
    }
    if bytes.last() == Some(&b'\r') {
        bytes.pop();
    }
    let text = String::from_utf8(bytes).map_err(|error| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            format!("backend output emitted invalid UTF-8: {error}"),
        )
    })?;
    Ok(Some(NdjsonLine {
        text,
        raw_byte_count,
        terminated,
    }))
}

pub(super) async fn read_ndjson_line<R: AsyncBufRead + Unpin>(
    reader: &mut R,
    line_limit: usize,
) -> io::Result<Option<String>> {
    Ok(read_line_record(reader, line_limit)
        .await?
        .map(|line| line.text))
}

pub(super) async fn read_bounded_ndjson_output<R: AsyncRead + Unpin>(
    reader: &mut R,
    total_limit: usize,
    line_limit: usize,
) -> io::Result<String> {
    let mut reader = BufReader::new(reader);
    let mut output = String::new();
    let mut raw_byte_count = 0_usize;
    while let Some(line) = read_line_record(&mut reader, line_limit).await? {
        raw_byte_count = raw_byte_count.saturating_add(line.raw_byte_count);
        if raw_byte_count > total_limit {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!("backend output exceeded the {total_limit}-byte contract limit"),
            ));
        }
        output.push_str(&line.text);
        if line.terminated {
            output.push('\n');
        }
    }
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::{read_bounded_ndjson_output, read_ndjson_line};
    use tokio::io::BufReader;

    #[tokio::test]
    async fn line_reader_accepts_a_final_line_without_newline() {
        let mut input = BufReader::new(&b"final"[..]);
        assert_eq!(
            read_ndjson_line(&mut input, 5).await.expect("line"),
            Some("final".to_string())
        );
        assert_eq!(read_ndjson_line(&mut input, 5).await.expect("eof"), None);
    }

    #[tokio::test]
    async fn line_reader_rejects_invalid_utf8() {
        let mut input = BufReader::new(&[0xff, b'\n'][..]);
        let error = read_ndjson_line(&mut input, 8)
            .await
            .expect_err("invalid UTF-8 must fail");
        assert_eq!(error.kind(), std::io::ErrorKind::InvalidData);
        assert!(error.to_string().contains("invalid UTF-8"));
    }

    #[tokio::test]
    async fn line_reader_rejects_an_oversized_long_task_line() {
        let mut input = BufReader::new(&b"12345\n"[..]);
        let error = read_ndjson_line(&mut input, 4)
            .await
            .expect_err("the long-task reader must enforce the shared line limit");
        assert!(error.to_string().contains("output line"));
        assert!(error.to_string().contains("4-byte contract limit"));
    }

    #[tokio::test]
    async fn one_shot_reader_rejects_an_oversized_line_below_the_total_limit() {
        let mut input = &b"12345\n6\n"[..];
        let error = read_bounded_ndjson_output(&mut input, 32, 4)
            .await
            .expect_err("the first line exceeds its independent limit");
        assert!(error.to_string().contains("output line"));
        assert!(error.to_string().contains("4-byte contract limit"));
    }

    #[tokio::test]
    async fn one_shot_reader_rejects_aggregate_output_overflow() {
        let mut input = &b"123\n456\n"[..];
        let error = read_bounded_ndjson_output(&mut input, 7, 4)
            .await
            .expect_err("aggregate output exceeds its limit");
        assert!(error.to_string().contains("7-byte contract limit"));
    }

    #[tokio::test]
    async fn one_shot_reader_rejects_invalid_utf8() {
        let mut input = &[0xff, b'\n'][..];
        let error = read_bounded_ndjson_output(&mut input, 8, 8)
            .await
            .expect_err("one-shot stdout must use the shared UTF-8 validation");
        assert!(error.to_string().contains("invalid UTF-8"));
    }

    #[tokio::test]
    async fn one_shot_reader_preserves_valid_multiline_output() {
        let mut input = &b"123\n456\nlast"[..];
        let output = read_bounded_ndjson_output(&mut input, 12, 5)
            .await
            .expect("bounded output");
        assert_eq!(output, "123\n456\nlast");
    }
}
