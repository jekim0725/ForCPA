def calculate_straight_line(cost, residual_value, useful_life):
    depreciable_amount = cost - residual_value
    annual_depreciation = depreciable_amount / useful_life

    schedule = []
    book_value = cost

    for year in range(1, useful_life + 1):
        book_value -= annual_depreciation

        schedule.append(
            {
                "year": year,
                "depreciation": annual_depreciation,
                "book_value": book_value,
            }
        )

    return schedule


cost = int(input("취득원가를 입력하세요: "))
residual_value = int(input("잔존가치를 입력하세요: "))
useful_life = int(input("내용연수를 입력하세요: "))

schedule = calculate_straight_line(
    cost,
    residual_value,
    useful_life,
)

print("\n연도 | 감가상각비 | 기말 장부가액")
print("-" * 38)

for row in schedule:
    print(
        f"{row['year']:>4} | "
        f"{row['depreciation']:>12,.0f}원 | "
        f"{row['book_value']:>13,.0f}원"
    )