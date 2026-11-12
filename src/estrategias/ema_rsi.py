from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd

class EstrategiaEMARSI(Strategy):
    ema_rapida = 10
    ema_lenta = 50
    rsi_umbral = 60
    stop_loss_pct = 0.02
    take_profit_pct = 0.03
    
    def init(self):
        self.ema_rapida = self.I(lambda x: pd.Series(x).ewm(span=self.ema_rapida).mean(), self.data.Close)
        self.ema_lenta = self.I(lambda x: pd.Series(x).ewm(span=self.ema_lenta).mean(), self.data.Close)
        
        def rsi(prices, period=14):
            delta = pd.Series(prices).diff()
            gain = delta.where(delta > 0, 0).rolling(period).mean()
            loss = -delta.where(delta < 0, 0).rolling(period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        self.rsi = self.I(rsi, self.data.Close)
    
    def next(self):
        if crossover(self.ema_rapida, self.ema_lenta) and self.rsi[-1] < self.rsi_umbral:
            if not self.position:
                precio_entrada = self.data.Close[-1]
                stop_loss = precio_entrada * (1 - self.stop_loss_pct)
                take_profit = precio_entrada * (1 + self.take_profit_pct)
                self.buy(sl=stop_loss, tp=take_profit)
        elif crossover(self.ema_lenta, self.ema_rapida):
            if self.position:
                self.position.close()
