#!/usr/bin/env python3
"""TCP-like reliable data transfer protocol simulator with sliding window."""

import random
from collections import deque


class Packet:
    """Represents a data packet with sequence number and payload."""
    def __init__(self, seq, data=""):
        self.seq = seq
        self.data = data
        self.ack = -1

    def __repr__(self):
        return f"Packet(seq={self.seq}, data={self.data!r}, ack={self.ack})"


class ReliableTransport:
    """Sliding window protocol with retransmission and flow control."""

    def __init__(self, window_size=4, loss_rate=0.1):
        self.window_size = window_size
        self.loss_rate = loss_rate

        # Sender state
        self.base = 0              # oldest unacknowledged seq
        self.next_seq = 0          # next sequence number to assign
        self.window = deque()      # packets available for receiver to pick up
        self.unacked = {}          # seq -> Packet for all unacked packets

        # Receiver state
        self.expected_seq = 0
        self.received = set()      # out-of-order packets buffered
        self.buffer = deque()      # ordered delivery buffer

        # Stats
        self.total_sent = 0
        self.total_retransmitted = 0
        self.total_lost = 0
        self.total_acked = 0

    def _should_drop(self):
        """Simulate random packet loss."""
        return random.random() < self.loss_rate

    def send(self, data):
        """Send data, chunking into packets within the sliding window.
        Returns list of Packet objects sent."""
        chunks = [data[i:i+20] for i in range(0, len(data), 20)]
        sent = []

        for chunk in chunks:
            # Flow control: only send if window has room
            if len(self.window) >= self.window_size:
                break  # window full, stop sending

            pkt = Packet(self.next_seq, chunk)
            self.window.append(pkt)       # available for receiver
            self.unacked[self.next_seq] = pkt  # track for ACK processing
            self.next_seq += 1
            sent.append(pkt)

        return sent

    def receive(self):
        """Receiver picks one packet from the sender's window.
        Simulates network delivery with possible loss.
        Returns (data, seq) or None."""
        if not self.window:
            return None

        pkt = self.window.popleft()

        # Simulate network loss
        if self._should_drop():
            self.total_lost += 1
            return None

        # Receiver processes the packet
        if pkt.seq == self.expected_seq:
            self.buffer.append(pkt.data)
            self.expected_seq += 1
            # Deliver consecutive out-of-order packets
            while self.expected_seq in self.received:
                self.received.remove(self.expected_seq)
                self.buffer.append(self.unacked[self.expected_seq].data)
                del self.unacked[self.expected_seq]
                self.expected_seq += 1
        else:
            # Out-of-order: buffer it for later delivery
            self.received.add(pkt.seq)

        self.total_sent += 1
        return pkt.data, pkt.seq

    def acknowledge(self, seq):
        """Process ACK from receiver. Slides window and triggers retransmissions."""
        if seq not in self.unacked:
            return self.base, self.next_seq

        # Remove acked packet
        del self.unacked[seq]
        self.total_acked += 1

        # Slide window forward
        while self.base in self.unacked:
            del self.unacked[self.base]
            self.base += 1

        # Retransmit unacked packets
        for s in list(self.unacked.keys()):
            pkt = Packet(s, self.unacked[s].data)
            self.window.append(pkt)
            self.total_retransmitted += 1

        return self.base, self.next_seq

    def has_pending(self):
        """Check if there are still unacknowledged packets."""
        return bool(self.window or self.unacked)

    def get_stats(self):
        return {
            "packets_sent": self.total_sent,
            "retransmissions": self.total_retransmitted,
            "packets_lost": self.total_lost,
            "packets_acked": self.total_acked,
            "window_base": self.base,
            "window_next": self.next_seq,
        }


def main():
    random.seed(42)
    print("=" * 60)
    print("TCP-like Reliable Data Transfer Protocol Simulator")
    print("=" * 60)
    print(f"Window size: 4  |  Loss rate: 10%  |  Chunk size: 20 bytes")
    print("-" * 60)

    sender = ReliableTransport(window_size=4, loss_rate=0.1)
    receiver = ReliableTransport(window_size=4, loss_rate=0.0)

    message = "Hello from the sender! " * 10  # 230 bytes
    print(f"Sending message ({len(message)} bytes):")
    print(f"  {message!r}")
    print()

    # Phase 1: Initial send (fills window up to window_size)
    initial = sender.send(message)
    print(f"[S] Enqueued {len(initial)} packets (seq 0-{len(initial)-1})")
    print(f"    Window: {len(sender.window)}, Unacked: {len(sender.unacked)}")
    print()

    # Phase 2: Simulation loop
    full_data = b""
    rounds = 0
    max_rounds = 200

    while sender.has_pending() and rounds < max_rounds:
        rounds += 1

        # Receiver picks up one packet
        result = receiver.receive()
        if result is None:
            continue

        data, seq = result
        full_data += data.encode() if isinstance(data, str) else data
        print(f"[R] seq={seq}: {data!r}")

        # Sender processes ACK and handles retransmission
        base, nxt = sender.acknowledge(seq)
        print(f"[S] ACK={seq} -> window [{base}, {nxt}) "
              f"(window: {len(sender.window)}, unacked: {len(sender.unacked)})")

    print()
    if rounds >= max_rounds:
        print("[!] Reached max rounds - protocol stuck")
    else:
        print("-" * 60)
        print(f"Received ({len(full_data)} bytes): {full_data!r}")
        print(f"Correct: {full_data.decode() == message}")
        print()

        stats = sender.get_stats()
        print("Protocol Statistics:")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        print("=" * 60)


if __name__ == "__main__":
    main()
