def calculate_straight_line(cost, residual_value, useful_life):
    depreciable_amount = cost - residual_value
    annual_depreciation = depreciable_amount / useful_life

    return annual_depreciation


cost = int(input("취득원가를 입력하세요: "))
residual_value = int(input("잔존가치를 입력하세요: "))
useful_life = int(input("내용연수를 입력하세요: "))

annual_depreciation = calculate_straight_line(
    cost,
    residual_value,
    useful_life,
)

print(f"연간 감가상각비: {annual_depreciation:,.0f}원")