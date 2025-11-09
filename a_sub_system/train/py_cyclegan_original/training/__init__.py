"""Training Module for CycleGAN"""
from .losses import CycleLoss, AdversarialLoss, IdentityLoss

__all__ = ["CycleLoss", "AdversarialLoss", "IdentityLoss"]
