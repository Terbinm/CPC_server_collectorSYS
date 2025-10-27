import torch.nn as nn
from torch.nn import functional as F


class MotorGeneratorlinear(nn.Module):


    """馬達發電機線性自編碼器模型
    參數:
        input_dim (int): 輸入維度，應為輸入特徵數量
        hidden_dim (int): 隱藏層維度，預設為 256
    """
    def __init__(self, input_dim=9, hidden_dim=256):
        super().__init__()
        # 注意：input_dim 需要包含位置編碼的維度
        actual_input_dim = input_dim +1  # +1 為位置編碼

        self.encoder = nn.Sequential(
            nn.Linear(actual_input_dim, 64),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(64),
            # nn.Dropout(0.1),
            nn.Linear(64, 128),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(128),
            # nn.Dropout(0.1),
            nn.Linear(128, hidden_dim),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(hidden_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(128),
            # nn.Dropout(0.1),
            nn.Linear(128, 64),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(64),
            nn.Linear(64, input_dim),  # 輸出維度為 input_dim-1 (26維)
            nn.Tanh()
        )

    def forward(self, x):
        x = self.encoder(x)
        x = self.decoder(x)
        return x

class MotorDiscriminatorLinear(nn.Module):


    """馬達發電機線性自編碼器模型
    參數:
        input_dim (int): 輸入維度，應為輸入特徵數量
        hidden_dim (int): 隱藏層維度，預設為 256
    """
    def __init__(self, input_dim=9):
        super().__init__()
        actual_input_dim = input_dim +1 # +1 為位置編碼

        self.model = nn.Sequential(
            nn.Linear(actual_input_dim, 128),
            nn.LeakyReLU(0.2),
            # nn.Dropout(0.1),
            nn.BatchNorm1d(128),
            nn.Linear(128, 64),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(64),
            nn.Linear(64, 32),
            nn.LeakyReLU(0.2),
            # nn.Dropout(0.1),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.model(x)