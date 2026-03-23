#!/bin/bash
set -e

iface="$(ip route show default | awk '{print $5; exit}')"
inip="$(ip addr show dev "$iface" | awk '/inet /{print $2; exit}')"
ingw="$(ip route show default dev "$iface" | awk '{print $3; exit}')"

tunctl -t tap0 -u `whoami`
ip link set tap0 up
ip link add br0 type bridge
ip link set tap0 master br0
ip link set dev "$iface" down
ip addr flush dev "$iface"
ip link set dev "$iface" up
ip link set dev "$iface" master br0
ip link set br0 up

worker_ip="${inip%/*}"  # strip the /24 CIDR suffix

ip addr add $inip brd + dev br0
route add default gw $ingw dev br0

# If ALLOW_VM_INTERNET is explicitly set to "false", block all forwarded traffic
# from the tap interface except to this worker's own IP.
# The VM still reaches server.py on this container (for binary download and log
# uploads) but cannot reach the internet or any other container on sandboxnet.
if [ "${ALLOW_VM_INTERNET:-true}" = "false" ]; then
    echo "VM internet access disabled — restricting tap0 forwarding to worker IP $worker_ip only"
    iptables -I FORWARD -i tap0 -d "$worker_ip" -j ACCEPT
    iptables -I FORWARD -i tap0 -j DROP
fi

(while true; do python3 server.py; echo "server.py exited, restarting..."; sleep 2; done) &
python3 poller.py



