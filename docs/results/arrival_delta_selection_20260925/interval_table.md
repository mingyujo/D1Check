# 12조건의 정확한 허용폭 구간

δ 단위 %p. 구간은 [왼쪽, 오른쪽), ∞는 이후 동일. 이름은 동결된 PC 정책이다. 사후 oracle 참고이며 배포 정책이 아니다.

| 조건 | δ 구간 | 제약 충족 정책 | 긴급 P95 최저 정책(동률 모두) | 긴급 ms |
|---|---|---|---|---:|
| low | [0, ∞) | CPU urgent, Fixed split, B2, B3, P | CPU urgent, Fixed split, B3, P | 158.365 |
| queue | [0, 340/9) | CPU urgent, B2, B3, P | B2 | 425.889 |
| queue | [340/9, ∞) | CPU urgent, Fixed split, B2, B3, P | Fixed split | 206.911 |
| burst | [0, 50) | CPU urgent, B2, B3, P | B2 | 501.831 |
| burst | [50, ∞) | CPU urgent, Fixed split, B2, B3, P | Fixed split | 205.581 |
| urgent_heavy | [0, 50) | CPU urgent, B2, B3, P | B2 | 698.899 |
| urgent_heavy | [50, ∞) | CPU urgent, Fixed split, B2, B3, P | Fixed split | 206.911 |
| classification_mix | [0, 50/3) | CPU urgent, B2, B3, P | B2 | 603.766 |
| classification_mix | [50/3, ∞) | CPU urgent, Fixed split, B2, B3, P | Fixed split | 205.486 |
| reverse | [0, ∞) | CPU urgent, Fixed split, B2, B3, P | CPU urgent | 764.432 |
| queue_interference_1.0 | [0, 340/9) | CPU urgent, B2, B3, P | B2 | 305.690 |
| queue_interference_1.0 | [340/9, ∞) | CPU urgent, Fixed split, B2, B3, P | Fixed split | 159.200 |
| queue_interference_2.0 | [0, 40/9) | CPU urgent | CPU urgent | 595.494 |
| queue_interference_2.0 | [40/9, 140/9) | CPU urgent, B2 | B2 | 546.088 |
| queue_interference_2.0 | [140/9, 220/9) | CPU urgent, B2, B3 | B2 | 546.088 |
| queue_interference_2.0 | [220/9, 350/9) | CPU urgent, B2, B3, P | B2 | 546.088 |
| queue_interference_2.0 | [350/9, ∞) | CPU urgent, Fixed split, B2, B3, P | Fixed split | 254.622 |
| queue_estimate_0.75 | [0, 10/9) | CPU urgent, B2, B3 | B2 | 425.889 |
| queue_estimate_0.75 | [10/9, 340/9) | CPU urgent, B2, B3, P | B2 | 425.889 |
| queue_estimate_0.75 | [340/9, ∞) | CPU urgent, Fixed split, B2, B3, P | Fixed split | 206.911 |
| queue_estimate_1.25 | [0, 340/9) | CPU urgent, B2, B3, P | B2 | 425.889 |
| queue_estimate_1.25 | [340/9, ∞) | CPU urgent, Fixed split, B2, B3, P | Fixed split | 206.911 |
| queue_load_x2 | [0, 250/9) | CPU urgent, B2, B3, P | B2 | 490.882 |
| queue_load_x2 | [250/9, ∞) | CPU urgent, Fixed split, B2, B3, P | Fixed split | 270.390 |
| queue_hostcost_x10 | [0, 320/9) | CPU urgent, B2, B3, P | B2 | 428.589 |
| queue_hostcost_x10 | [320/9, ∞) | CPU urgent, Fixed split, B2, B3, P | Fixed split | 209.611 |
