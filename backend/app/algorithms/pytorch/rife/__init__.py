"""Side-effect-free package for RIFE model implementations.

Import concrete modules such as ``solver`` or ``model_loader`` directly so
package import never loads PyTorch into a Paddle worker process.
"""
