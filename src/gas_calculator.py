from decimal import Decimal
class GasCalculator:
    """Estimate gas spending and net profit in ETH terms."""

    # 以 ETH 估算：单次交易 gas_used * gas_price(gwei) / 1e9
    def calculate_total_gas_cost(self, trade_count: int, avg_gas_price_gwei: Decimal, avg_gas_used: int = 180000) -> int:
        """Return the total gas cost across a number of transactions."""
        gas_price_wei = int(Decimal(avg_gas_price_gwei) * Decimal(1_000_000_000))      # Gwei → Wei
        gas_used_int = int(avg_gas_used)                             # 取整
        return trade_count * gas_used_int * gas_price_wei

    def calculate_net_profit(self, 
        gross_profit: Decimal, 
        trade_count: int, 
        avg_gas_price_gwei: Decimal, 
        avg_gas_used: int = 180000) -> tuple[Decimal, int]:
        total_gas_cost_wei = self.calculate_total_gas_cost(trade_count, avg_gas_price_gwei, avg_gas_used)
        total_gas_cost_eth = Decimal(total_gas_cost_wei) / Decimal(1_000_000_000_000_000_000)   # Wei → ETH
        return gross_profit - total_gas_cost_eth, total_gas_cost_wei
