import pytorch_lightning as pl
import torch
from torch.nn import functional as F
import numpy as np
from torchaudio import transforms

from cycleGan_model import MotorGeneratorlinear, MotorDiscriminatorLinear
from torch import nn
import os
import json


class PlMotorModule(pl.LightningModule):


    """
    參數:
        input_dim (int): 輸入維度，應為輸入特徵數量
    """
    def __init__(self, pl_set_input_dim=9):
        super().__init__()
        self.automatic_optimization = False

        print(f"PlMotorModule - pl_set_input_dim: {pl_set_input_dim}")

        self.generator_A_to_B = MotorGeneratorlinear(input_dim=pl_set_input_dim)
        self.generator_B_to_A = MotorGeneratorlinear(input_dim=pl_set_input_dim)

        self.discriminator_A = MotorDiscriminatorLinear(input_dim=pl_set_input_dim)
        self.discriminator_B = MotorDiscriminatorLinear(input_dim=pl_set_input_dim)

        self.mse_loss = nn.MSELoss()
        self.bce_loss = nn.BCEWithLogitsLoss()

        self.spectrogram = transforms.Spectrogram(n_fft=127, power=None)

    def forward(self, z):
        return self.generator_A_to_B(z)

    def configure_optimizers(self):
        opt_g_a2b = torch.optim.Adam(self.generator_A_to_B.parameters())
        opt_g_b2a = torch.optim.Adam(self.generator_B_to_A.parameters())
        opt_d_a = torch.optim.Adam(self.discriminator_A.parameters())
        opt_d_b = torch.optim.Adam(self.discriminator_B.parameters())

        return [opt_g_a2b, opt_g_b2a, opt_d_a, opt_d_b], []

    def training_step(self, batch, batch_idx, b_hat_hat=None):
        a_feat, b_feat = batch

        # a_spec = torch.concat((a_spec.real, a_spec.imag), dim=1)
        # b_spec = torch.concat((b_spec.real, b_spec.imag), dim=1)

        # a, b = self.spectrogram(a), self.spectrogram(b)
        opt_g_a2b, opt_g_b2a, opt_d_a, opt_d_b = self.optimizers()

        b_hat = self.generator_A_to_B(a_feat)
        a_hat = self.generator_B_to_A(b_feat)

        # discriminator A
        self.toggle_optimizer(opt_d_a)
        a_dis_real_hat = self.discriminator_A(a_feat)
        a_dis_fake_hat = self.discriminator_A(torch.cat((a_hat.detach(), a_feat[:, -1].unsqueeze(1)), dim=1))

        a_dis_real = torch.ones(a_feat.size(0), 1)
        a_dis_real = a_dis_real.type_as(a_feat)

        a_dis_fake = torch.zeros(a_feat.size(0), 1)
        a_dis_fake = a_dis_fake.type_as(a_feat)

        a_dis_loss = (
                             self.bce_loss(a_dis_real_hat, a_dis_real) +
                             self.bce_loss(a_dis_fake_hat, a_dis_fake)
                     ) / 2

        a_dis_acc = (
                            torch.sum(a_dis_real_hat > 0.5).item() / a_dis_real_hat.size(0) +
                            torch.sum(a_dis_fake_hat < 0.5).item() / a_dis_fake_hat.size(0)
                    ) / 2

        self.manual_backward(a_dis_loss)
        opt_d_a.step()
        opt_d_a.zero_grad()
        self.untoggle_optimizer(opt_d_a)

        # discriminator B
        self.toggle_optimizer(opt_d_b)
        b_dis_real_hat = self.discriminator_B(b_feat)
        b_dis_fake_hat = self.discriminator_B(torch.cat((b_hat.detach(), b_feat[:, -1].unsqueeze(1)), dim=1))


        b_dis_real = torch.ones(b_feat.size(0), 1)
        b_dis_real = b_dis_real.type_as(b_feat)

        b_dis_fake = torch.zeros(b_feat.size(0), 1)
        b_dis_fake = b_dis_fake.type_as(b_feat)

        b_dis_loss = (
                             self.bce_loss(b_dis_real_hat, b_dis_real) +
                             self.bce_loss(b_dis_fake_hat, b_dis_fake)
                     ) / 2

        b_dis_acc = (
                            torch.sum(b_dis_real_hat > 0.5).item() / b_dis_real_hat.size(0) +
                            torch.sum(b_dis_fake_hat < 0.5).item() / b_dis_fake_hat.size(0)
                    ) / 2
        self.manual_backward(b_dis_loss)
        opt_d_b.step()
        opt_d_b.zero_grad()
        self.untoggle_optimizer(opt_d_b)

        # generator A to B
        self.toggle_optimizer(opt_g_a2b)
        b_hat_hat = self.generator_A_to_B(torch.cat((a_hat.detach(), a_feat[:, -1].unsqueeze(1)), dim=1))

        loss_b = self.mse_loss((torch.cat((b_hat, b_feat[:, -1].unsqueeze(1)), dim=1)), b_feat)
        cycle_loss_b = self.mse_loss((torch.cat((b_hat_hat, b_feat[:, -1].unsqueeze(1)), dim=1)), b_feat)

        # loss_b_all = loss_b * 0.2 + cycle_loss_b * 0.1 + self.bce_loss(a_dis_fake_hat, a_dis_real_hat).detach() * 0.7
        loss_b_all = loss_b * 0.1 + cycle_loss_b * 0.5 + self.bce_loss(a_dis_fake_hat, a_dis_real_hat).detach() * 0.4

        self.manual_backward(loss_b_all)
        opt_g_a2b.step()
        opt_g_a2b.zero_grad()
        self.untoggle_optimizer(opt_g_a2b)

        # generator B to A
        self.toggle_optimizer(opt_g_b2a)
        a_hat_hat = self.generator_B_to_A(torch.cat((b_hat.detach(), b_feat[:, -1].unsqueeze(1)), dim=1))

        loss_a = self.mse_loss((torch.cat((a_hat, a_feat[:, -1].unsqueeze(1)), dim=1)), a_feat)
        cycle_loss_a = self.mse_loss((torch.cat((a_hat_hat, a_feat[:, -1].unsqueeze(1)), dim=1)), a_feat)

        # loss_a_all = loss_a * 0.2 + cycle_loss_a * 0.1 + self.bce_loss(b_dis_fake_hat, b_dis_real_hat).detach() * 0.7
        loss_a_all = loss_a * 0.1 + cycle_loss_a * 0.5 + self.bce_loss(b_dis_fake_hat, b_dis_real_hat).detach() * 0.4

        self.manual_backward(loss_a_all)
        opt_g_b2a.step()
        opt_g_b2a.zero_grad()
        self.untoggle_optimizer(opt_g_b2a)

        generator_losses = {
            "A_to_B": loss_b,
            "B_to_A": loss_a,
            "A_to_B_to_A": cycle_loss_a,
            "B_to_A_to_B": cycle_loss_b,
        }
        discriminator_losses = {
            "A": a_dis_loss,
            "B": b_dis_loss,
        }
        discriminator_acc = {
            "A": a_dis_acc,
            "B": b_dis_acc,
        }

        self.logger.experiment.add_scalars('generator_loss', generator_losses, self.global_step)
        self.logger.experiment.add_scalars('discriminator_loss', discriminator_losses, self.global_step)
        self.logger.experiment.add_scalars('discriminator_acc', discriminator_acc, self.global_step)

        self.log("total_loss", (loss_a + loss_b + cycle_loss_a + cycle_loss_b) / 4, prog_bar=True)

    def validation_step(self, batch, batch_idx):
        a_feat, b_feat = batch
        # a, b, a_feat, b_feat = batch
        # a_spec, b_spec = self.spectrogram(a), self.spectrogram(b)

        # a_spec = torch.concat((a_spec.real, a_spec.imag), dim=1)
        # b_spec = torch.concat((b_spec.real, b_spec.imag), dim=1)

        b_hat = self.generator_A_to_B(a_feat)
        a_hat = self.generator_B_to_A(b_feat)

        b_hat_hat = self.generator_A_to_B(torch.cat((a_hat.detach(), a_feat[:, -1].unsqueeze(1)), dim=1))
        b_loss = self.mse_loss((torch.cat((b_hat, b_feat[:, -1].unsqueeze(1)), dim=1)), b_feat)
        b_cycle_loss = self.mse_loss((torch.cat((b_hat_hat, b_feat[:, -1].unsqueeze(1)), dim=1)), b_feat)

        a_hat_hat = self.generator_B_to_A(torch.cat((b_hat.detach(), b_feat[:, -1].unsqueeze(1)), dim=1))
        a_loss = self.mse_loss((torch.cat((a_hat, a_feat[:, -1].unsqueeze(1)), dim=1)), a_feat)
        a_cycle_loss = self.mse_loss((torch.cat((a_hat_hat, a_feat[:, -1].unsqueeze(1)), dim=1)), a_feat)

        val_generator_losses = {
            "A_to_B": b_loss,
            "B_to_A": a_loss,
            "A_to_B_to_A": a_cycle_loss,
            "B_to_A_to_B": b_cycle_loss,
        }

        self.logger.experiment.add_scalars('val_generator_loss', val_generator_losses, self.global_step)

#             "A_to_B": b_loss,
#             "B_to_A": a_loss,
#         }
#
#         self.logger.experiment.add_scalars('val_generator_loss', val_generator_losses, self.global_step)
#         self.log("total_loss", (a_loss + b_loss) / 2, prog_bar=True)
