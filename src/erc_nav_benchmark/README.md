# ERC NAV BENCHMARK

Automated navigation testing harness for ERC (European Rover Challenge) simulation.  
Built on **ROS 2** + **Gazebo Classic**, inspired by the BARN Challenge architecture.

---

## Prerequisites

| Requirement | Version |
|---|---|
| ROS 2 | Humble (recommended) or Iron |
| Gazebo | Classic 11 (`gazebo_ros_pkgs`) |
| Python | 3.10+ |
| OS | Ubuntu 22.04 |

```bash
sudo apt install ros-humble-gazebo-ros-pkgs ros-humble-rviz2
pip3 install pyyaml
```

---

## Build

```bash
# From your ROS 2 workspace root (e.g. ~/ros2_ws/src)
# Copy/clone the erc_nav_benchmark folder here, then:

cd ~/ros2_ws
colcon build --packages-select erc_nav_benchmark
source install/setup.bash
```

> **Using your own rover model?**  
> Replace `models/erc_rover/model.sdf` with your URDF/SDF.  
> Ensure it has the `libgazebo_ros_diff_drive.so` plugin publishing to `/cmd_vel` and `/odom`,  
> and the `libgazebo_ros_bumper.so` plugin publishing to `/bumper_states`.

---

## Run

### One-command launch
```bash
python3 run_benchmark.py --level 1        # Easy
python3 run_benchmark.py --level 2        # Medium
python3 run_benchmark.py --level 3        # Hard
python3 run_benchmark.py --level 1 --rviz # + RViz visualizer
```

### Or via ros2 launch directly
```bash
ros2 launch erc_nav_benchmark benchmark.launch.py level:=1
ros2 launch erc_nav_benchmark benchmark.launch.py level:=2 teleop:=false
```

---

## Controls (Teleop)

| Key | Action |
|---|---|
| `W` / `↑` | Forward |
| `S` / `↓` | Backward |
| `A` / `←` | Turn left |
| `D` / `→` | Turn right |
| `Q` | Spin left (in-place) |
| `E` | Spin right (in-place) |
| `+` | Increase speed |
| `-` | Decrease speed |
| `SPACE` | Emergency stop |
| `X` | Quit teleop |

---

## Levels

| Level | Obstacles | Timeout | Notes |
|---|---|---|---|
| 1 | 6 rocks, sparse | 120s | Open terrain, easy routing |
| 2 | 14 obstacles, clustered | 180s | Mid-field barrier with gap |
| 3 | 22 obstacles, corridors | 240s | Slalom zones, tight passages |

---

## Scoring

The score formula is inspired by the BARN Challenge:

```
score = (checkpoints/4) × (optimal_time/actual_time) × smoothness_multiplier
```

| Smoothness Index | Multiplier |
|---|---|
| High (low variance) | 1.0 |
| Moderate | 0.8 |
| Poor (erratic) | 0.5 |

**Crash → score = 0.0 immediately.**

---

## Sample Report Output

```
============================================================
           ERC NAV BENCHMARK RUN TERMINATION REPORT        
============================================================
Test Scenario ID             : Level_1
Final Run Status             : Target Reached
Checkpoints Cleared          : 4 / 4
Sequence Compliance Status   : PASSED
Total Traversal Latency      : 45.23 seconds
Actual Distance Traveled     : 12.45 meters
Normalized Performance Score : 0.7823
Driving Smoothness Index     : High
============================================================
```

Reports are saved to `logs/` automatically.

---

## Project Structure

```
erc_nav_benchmark/
├── run_benchmark.py              ← ONE-COMMAND LAUNCHER
├── package.xml
├── CMakeLists.txt
├── erc_nav_benchmark/
│   ├── judging_engine.py         ← Core benchmark node
│   ├── teleop_node.py            ← Keyboard driving
│   └── waypoint_publisher.py     ← RViz markers
├── launch/
│   └── benchmark.launch.py       ← ROS 2 launch
├── worlds/
│   ├── level_1.world             ← Easy environment
│   ├── level_2.world             ← Medium environment
│   └── level_3.world             ← Hard environment
├── models/
│   └── erc_rover/
│       ├── model.sdf             ← Rover (swap with yours)
│       └── model.config
├── config/
│   └── waypoints.yaml            ← Waypoint positions per level
└── logs/                         ← Auto-saved run reports
```

---

## Proving the System Works

Run the benchmark **twice** on Level 1:

1. **Smooth run** — steady WASD driving, no crashes  
   → Expect score ≥ 0.6, Smoothness: High

2. **Erratic run** — rapid key-mashing, maybe crash  
   → Expect score ≤ 0.3 or 0.0, Smoothness: Poor

If the system produces different scores → **benchmarking system is working correctly.**

---

## Viewing Past Reports

```bash
python3 run_benchmark.py --list-logs
```
