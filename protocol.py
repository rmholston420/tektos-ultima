#!/usr/bin/env python3
"""TCP-like reliable data transfer protocol simulator with sliding window."""

import random
import time
from collections import deque

SEED = 42
PACKET_SIZE = 64
MAX_WINDOW = 8
LOSS_RATE = 0.15  # 15% packet drop probability


class Packet:
    """Represents a data packet."""

    def __init__(self, seq, data, ack_num=None):
        self.seq = seq
        self.data = data
        self.ack_num = ack_num
        self.timestamp = time.time()

    def __repr__(self):
        return f"Packet(seq={self.seq}, data='{self.data[:20]}...')"


class ReliableTransport:
    """Sliding window protocol with retransmission and flow control."""

    def __init__(self, window_size=MAX_WINDOW, loss_rate=LOSS_RATE):
        self.window_size = window_size
        self.loss_rate = loss_rate
        self.seq_num = 0
        self.base = 0  # oldest unacknowledged sequence
        self.next_seq = 0  # next sequence to send
        self.acked = set()
        self.pending = {}  # seq -> Packet
        self.unacked = set()  # set of sequence numbers not yet acked
        self.receiver_buffer = deque()
        self._lost_packets = 0
        self._sent_packets = 0
        self._received_packets = 0

    def _should_drop(self):
        """Simulate random packet loss."""
        return random.random() < self.loss_rate

    def send(self, data):
        """Send a chunk of data using sliding window. Returns list of packets."""
        packets = []
        for i in range(0, len(data), PACKET_SIZE):
            chunk = data[i : i + PACKET_SIZE]
            pkt = Packet(self.seq_num, chunk)
            self.seq_num += 1

            # Check window limit
            if self.next_seq - self.base >= self.window_size:
                break

            # Simulate loss
            if self._should_drop():
                self._lost_packets += 1
                print(f"  [LOSS] Packet {pkt.seq} dropped in transit")
            else:
                self.pending[pkt.seq] = pkt
                self.unacked.add(pkt.seq)
                packets.append(pkt)
                self._sent_packets += 1
                print(f"  [SENT] Packet {pkt.seq}: '{chunk[:30]}...'")

            self.next_seq += 1
        return packets

    def receive(self, pkt):
        """Receiver accepts a packet. Returns acknowledgment."""
        self._received_packets += 1
        self.receiver_buffer.append(pkt)
        ack = Packet(0, None, ack_num=pkt.seq + 1)  # cumulative ACK
        print(f"  [RCVD] Packet {pkt.seq} -> ACK {ack.ack_num}")
        return ack

    def acknowledge(self, ack):
        """Process acknowledgment, advance window, retransmit if needed."""
        # Mark all packets up to ack number as acknowledged
        while self.base < ack.ack_num:
            if self.base in self.unacked:
                self.acked.add(self.base)
                self.unacked.discard(self.base)
                if self.base in self.pending:
                    del self.pending[self.base]
                print(f"  [ACK] Packet {self.base} acknowledged")
            self.base += 1

        # Retransmit unacknowledged packets after timeout
        remaining = list(self.pending.items())
        for seq, pkt in remaining:
            if time.time() - pkt.timestamp > 0.05:  # 50ms timeout
                print(f"  [TIMEOUT] Retransmitting packet {seq}")
                if not self._should_drop():
                    self.pending[seq] = pkt
                    self._sent_packets += 1
                else:
                    self._lost_packets += 1
                    print(f"  [LOSS] Retransmitted packet {seq} also dropped")

    def get_stats(self):
        return {
            "sent": self._sent_packets,
            "lost": self._lost_packets,
            "received": self._received_packets,
            "acked": len(self.acked),
            "window_size": self.window_size,
            "loss_rate": self.loss_rate,
        }


def main():
    print("=" * 60)
    print("  TCP-like Reliable Data Transfer Simulator")
    print("=" * 60)

    # Message to send (larger than window to trigger retransmission)
    message = "Hello, this is a test message for the reliable transport protocol. " * 5
    print(f"\nMessage to send ({len(message)} bytes):")
    print(f"  '{message[:60]}...'")

    random.seed(SEED)
    transport = ReliableTransport(window_size=MAX_WINDOW, loss_rate=LOSS_RATE)

    # Simulate sending the message in chunks
    print(f"\n--- Window Size: {MAX_WINDOW}, Loss Rate: {LOSS_RATE:.0%} ---\n")

    all_packets = []
    while True:
        chunks_sent = transport.send(message)
        all_packets.extend(chunks_sent)
        if len(chunks_sent) < transport.window_size:
            break
        # Advance window after partial send
        if transport.pending:
            oldest = min(transport.pending)
            fake_ack = Packet(0, None, ack_num=oldest + 1)
            transport.acknowledge(fake_ack)

    # Simulate receiving packets and sending ACKs
    print("\n--- Receiving & Acknowledging ---\n")
    for pkt in all_packets:
        ack = transport.receive(pkt)
        transport.acknowledge(ack)

    # Re-acknowledge any remaining
    if transport.pending:
        for seq in sorted(transport.pending):
            pkt = transport.pending[seq]
            ack = transport.receive(pkt)
            transport.acknowledge(ack)

    # Collect delivered data
    delivered = "".join(p.data for p in transport.receiver_buffer)

    print(f"\n{'=' * 60}")
    print(f"  Results")
    print(f"{'=' * 60}")
    print(f"  Bytes sent:    {transport.get_stats()['sent']}")
    print(f"  Packets lost:  {transport.get_stats()['lost']}")
    print(f"  Packets rcvd:  {transport.get_stats()['received']}")
    print(f"  Packets acked: {transport.get_stats()['acked']}")
    print(f"  Data delivered: {len(delivered)} bytes")
    print(f"  Message match: {delivered == message}")
    print(f"\nDelivered data: '{delivered[:60]}...'")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
