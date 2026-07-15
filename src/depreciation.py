def calculate_straight_line(cost, residual_value, useful_life):
    depreciable_amount = cost - residual_value
    annual_depreciation = depreciable_amount / useful_life

    return annual_depreciation


cost = 10_000_000
residual_value = 1_000_000
useful_life = 5

annual_depreciation = calculate_straight_line(
    cost,
    residual_value,
    useful_life,
)

print(f"연간 감가상각비: {annual_depreciation:,.0f}원")