#!/bin/bash

# =================================================================================
# 配置区（命令索引从0开始，按需求配置即可，窗口会自动适应）
# =================================================================================

# --- 会话名称定义 ---
SESSION_NAME="main"

# --- 命令定义 ---
COMMANDS=(
# -- [0] -- #
' jtop '
# -- [1] -- #
' bash -c "sudo chmod 777 /dev/ttyACM0; roslaunch mavros px4.launch; exec bash" '
# -- [2] -- #
' bash -c "roslaunch realsense2_camera rs_camera.launch; exec bash" '
# -- [3] -- #
' bash -c "roslaunch vins Drone_250.launch; exec bash" '
# 如需更多命令，按上述形式附加在数组中即可
)

# =================================================================================
# 执行区（如无必要，请勿改动）
# =================================================================================

# 获取命令数量
readonly NUM_COMMANDS=${#COMMANDS[@]}

if [ $NUM_COMMANDS -eq 0 ]; then
    echo "命令数组为空。"
    exit 1
fi

# 自适应窗口分割
tmux new-session -d -s $SESSION_NAME
for i in $(seq 1 $(($NUM_COMMANDS - 1))); do
    if [ $(($i % 2)) -ne 0 ]; then #
        tmux split-window -h -t $SESSION_NAME:0
    else
        tmux split-window -v -t $SESSION_NAME:0
    fi
    tmux select-layout -t $SESSION_NAME:0 tiled
done

# 命令发送
for i in $(seq 0 $(($NUM_COMMANDS - 1))); do
    PANE_INDEX=$i
    tmux send-keys -t $SESSION_NAME:0.$PANE_INDEX "${COMMANDS[$i]}" C-m
done

# 附加到终端
tmux attach-session -t $SESSION_NAME
