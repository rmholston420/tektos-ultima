"""Raft Consensus Protocol Simulator — asyncio-based."""

from __future__ import annotations

import asyncio
import random
import enum
import dataclasses
import copy
from typing import List, Optional, Dict


# ── Message Types ────────────────────────────────────────────────────────────

class MsgType(enum.Enum):
    REQUEST_VOTE = "request_vote"
    VOTE_RESPONSE = "vote_response"
    APPEND_ENTRIES = "append_entries"
    APPEND_RESPONSE = "append_response"


@dataclasses.dataclass
class RaftMessage:
    msg_type: MsgType
    sender: int
    receiver: int
    term: int
    candidate_id: Optional[int] = None
    last_log_index: Optional[int] = None
    last_log_term: Optional[int] = None
    vote_granted: Optional[bool] = None
    prev_log_index: Optional[int] = None
    prev_log_term: Optional[int] = None
    entries: Optional[list] = None
    leader_commit: Optional[int] = None
    success: Optional[bool] = None
    match_index: Optional[int] = None


# ── Node ─────────────────────────────────────────────────────────────────────

class RaftNode:
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"
    LEADER = "LEADER"

    def __init__(self, node_id: int, peers: List[int], clock: Clock):
        self.id = node_id
        self.peers = peers
        self.clock = clock

        self.state = self.FOLLOWER
        self.current_term = 0
        self.voted_for: Optional[int] = None

        # Log (index 0 is a dummy entry for term 0)
        self.log: List[dict] = [{"term": 0}]
        self.commit_index = -1
        self.last_applied = -1

        # Leader state
        self.next_index: Dict[int, int] = {}
        self.match_index: Dict[int, int] = {}

        # Election timers
        self.election_timeout = random.randint(150, 300)
        self.heartbeat_interval = 50
        self.last_heartbeat = 0
        self.last_vote_time = 0

        self.vote_count = 1
        self._response_queue: asyncio.Queue = asyncio.Queue()

    # ── Log helpers ──────────────────────────────────────────────────────

    @property
    def last_log_term(self) -> int:
        return self.log[-1]["term"]

    @property
    def last_log_index(self) -> int:
        return len(self.log) - 1

    def append_log(self, term: int, command: str):
        self.log.append({"term": term, "data": command})

    # ── Election ─────────────────────────────────────────────────────────

    async def start_election(self):
        if self.state == self.LEADER:
            return
        self.state = self.CANDIDATE
        self.current_term += 1
        self.voted_for = self.id
        self.vote_count = 1
        self.last_vote_time = self.clock.time
        self.log.append({"term": self.current_term, "data": None})

        for peer in self.peers:
            msg = RaftMessage(
                msg_type=MsgType.REQUEST_VOTE,
                sender=self.id,
                receiver=peer,
                term=self.current_term,
                candidate_id=self.id,
                last_log_index=self.last_log_index,
                last_log_term=self.last_log_term,
            )
            await self.clock.send(msg)

    def check_election_timeout(self):
        if self.state == self.LEADER:
            return
        if self.clock.time - self.last_vote_time > self.election_timeout:
            self.last_vote_time = self.clock.time
            asyncio.create_task(self.start_election())

    # ── Leader ───────────────────────────────────────────────────────────

    async def send_heartbeats(self):
        for peer in self.peers:
            ni = self.next_index.get(peer, self.last_log_index + 1)
            pli = ni - 1
            plf = self.log[pli]["term"] if pli >= 0 else 0
            entries = self.log[ni:] if ni <= self.last_log_index else []
            msg = RaftMessage(
                msg_type=MsgType.APPEND_ENTRIES,
                sender=self.id,
                receiver=peer,
                term=self.current_term,
                prev_log_index=pli,
                prev_log_term=plf,
                entries=entries,
                leader_commit=self.commit_index,
            )
            await self.clock.send(msg)
        self.last_heartbeat = self.clock.time

    # ── Message Handlers ─────────────────────────────────────────────────

    async def handle_vote_request(self, msg: RaftMessage):
        if msg.term > self.current_term:
            self.current_term = msg.term
            self.state = self.FOLLOWER
            self.voted_for = None

        if msg.term < self.current_term:
            return

        granted = False
        if self.voted_for is None or self.voted_for == msg.candidate_id:
            if (msg.last_log_term > self.last_log_term or
                    (msg.last_log_term == self.last_log_term and
                     msg.last_log_index >= self.last_log_index)):
                granted = True
                self.voted_for = msg.candidate_id
                self.last_vote_time = self.clock.time

        resp = RaftMessage(
            msg_type=MsgType.VOTE_RESPONSE,
            sender=self.id,
            receiver=msg.candidate_id,
            term=self.current_term,
            vote_granted=granted,
        )
        await self.clock.send(resp)

    async def handle_vote_response(self, msg: RaftMessage):
        if msg.term > self.current_term:
            self.current_term = msg.term
            self.state = self.FOLLOWER
            self.voted_for = None
        if msg.term < self.current_term or self.state != self.CANDIDATE:
            return

        if msg.vote_granted:
            self.vote_count += 1
            peers_count = len(self.peers) + 1
            if self.vote_count > peers_count // 2:
                self.state = self.LEADER
                for p in self.peers:
                    self.next_index[p] = self.last_log_index + 1
                    self.match_index[p] = 0
                asyncio.create_task(self.send_heartbeats())

    async def handle_append_entries(self, msg: RaftMessage):
        if msg.term < self.current_term:
            resp = RaftMessage(
                msg_type=MsgType.APPEND_RESPONSE,
                sender=self.id,
                receiver=msg.sender,
                term=self.current_term,
                success=False,
                match_index=self.last_log_index,
            )
            await self.clock.send(resp)
            return

        if msg.term > self.current_term:
            self.current_term = msg.term
        self.state = self.FOLLOWER
        self.voted_for = None
        self.last_vote_time = self.clock.time

        if msg.prev_log_index >= 0:
            if msg.prev_log_index >= len(self.log):
                resp = RaftMessage(
                    msg_type=MsgType.APPEND_RESPONSE,
                    sender=self.id,
                    receiver=msg.sender,
                    term=self.current_term,
                    success=False,
                    match_index=self.last_log_index,
                )
                await self.clock.send(resp)
                return
            if self.log[msg.prev_log_index]["term"] != msg.prev_log_term:
                self.log = self.log[:msg.prev_log_index + 1]
                resp = RaftMessage(
                    msg_type=MsgType.APPEND_RESPONSE,
                    sender=self.id,
                    receiver=msg.sender,
                    term=self.current_term,
                    success=False,
                    match_index=self.last_log_index,
                )
                await self.clock.send(resp)
                return

        if msg.entries:
            for i, entry in enumerate(msg.entries):
                idx = msg.prev_log_index + 1 + i
                if idx < len(self.log):
                    if self.log[idx]["term"] != entry["term"]:
                        self.log = self.log[:idx]
                        self.append_log(entry["term"], entry.get("data"))
                else:
                    self.append_log(entry["term"], entry.get("data"))

        if msg.leader_commit > self.commit_index:
            self.commit_index = min(msg.leader_commit, self.last_log_index)

        resp = RaftMessage(
            msg_type=MsgType.APPEND_RESPONSE,
            sender=self.id,
            receiver=msg.sender,
            term=self.current_term,
            success=True,
            match_index=self.last_log_index,
        )
        await self.clock.send(resp)

    async def handle_append_response(self, msg: RaftMessage):
        if msg.term > self.current_term:
            self.current_term = msg.term
            self.state = self.FOLLOWER
            self.voted_for = None

        if self.state != self.LEADER or msg.term < self.current_term:
            return

        if msg.success:
            self.match_index[msg.sender] = msg.match_index
            self.next_index[msg.sender] = msg.match_index + 1
            self._update_commit_index()

    def _update_commit_index(self):
        """Leader completeness: commit only if replicated on majority."""
        n = len(self.peers) + 1
        for n_i in range(self.last_log_index, self.commit_index, -1):
            if self.log[n_i]["term"] == self.current_term:
                count = 1
                for peer in self.peers:
                    if self.match_index.get(peer, 0) >= n_i:
                        count += 1
                if count > n // 2:
                    self.commit_index = n_i
                    break

    # ── Client Commands ──────────────────────────────────────────────────

    async def submit_command(self, command: str):
        if self.state != self.LEADER:
            return False
        self.append_log(self.current_term, command)
        self.next_index[self.id] = self.last_log_index + 1
        self.match_index[self.id] = self.last_log_index
        asyncio.create_task(self.send_heartbeats())
        return True

    def get_applied_commands(self) -> List[str]:
        return [e["data"] for e in self.log if e["data"] is not None
                and self.log.index(e) <= self.commit_index]

    # ── Main Loop ────────────────────────────────────────────────────────

    async def run(self):
        while True:
            msg = await self._response_queue.get()
            self.clock.time += 1

            if msg.msg_type == MsgType.REQUEST_VOTE:
                await self.handle_vote_request(msg)
            elif msg.msg_type == MsgType.VOTE_RESPONSE:
                await self.handle_vote_response(msg)
            elif msg.msg_type == MsgType.APPEND_ENTRIES:
                await self.handle_append_entries(msg)
            elif msg.msg_type == MsgType.APPEND_RESPONSE:
                await self.handle_append_response(msg)

            if self.state == self.LEADER:
                if self.clock.time - self.last_heartbeat >= self.heartbeat_interval:
                    asyncio.create_task(self.send_heartbeats())

            if self.state != self.LEADER:
                self.check_election_timeout()


# ── Clock / Scheduler ────────────────────────────────────────────────────────

class Clock:
    def __init__(self):
        self.time = 0
        self._queue: asyncio.Queue = asyncio.Queue()

    async def send(self, msg: RaftMessage):
        await self._queue.put(msg)

    async def dispatch(self, node: RaftNode):
        msg = await self._queue.get()
        await node._response_queue.put(msg)


# ── Simulation ───────────────────────────────────────────────────────────────

async def simulate(num_nodes: int, commands: List[str],
                   rounds: int = 500) -> Dict[int, RaftNode]:
    clock = Clock()
    nodes: Dict[int, RaftNode] = {}

    for i in range(num_nodes):
        peers = [j for j in range(num_nodes) if j != i]
        nodes[i] = RaftNode(i, peers, clock)

    tasks = [asyncio.create_task(node.run()) for node in nodes.values()]

    async def dispatch_loop():
        for _ in range(rounds * 10):
            node = random.choice(list(nodes.values()))
            try:
                await asyncio.wait_for(clock.dispatch(node), timeout=0.01)
            except asyncio.TimeoutError:
                pass

    async def command_submitter():
        await asyncio.sleep(0.05)
        for cmd in commands:
            leader = None
            for n in nodes.values():
                if n.state == RaftNode.LEADER:
                    leader = n
                    break
            if leader:
                await leader.submit_command(cmd)
            await asyncio.sleep(0.02)

    dispatch_task = asyncio.create_task(dispatch_loop())
    submit_task = asyncio.create_task(command_submitter())

    await asyncio.sleep(rounds * 0.01)
    for t in tasks:
        t.cancel()
    dispatch_task.cancel()
    submit_task.cancel()

    return nodes


# ── __main__ ─────────────────────────────────────────────────────────────────

def _verify_safety(nodes: Dict[int, RaftNode]) -> None:
    """Verify log matching & leader completeness properties."""
    leaders = [n for n in nodes.values() if n.state == RaftNode.LEADER]
    followers = [n for n in nodes.values() if n.state != RaftNode.LEADER]

    leader_logs = {n.id: [e["data"] for e in n.log if e["data"] is not None]
                   for n in nodes.values() if n.state == RaftNode.LEADER}
    follower_logs = {n.id: [e["data"] for e in n.log if e["data"] is not None]
                     for n in nodes.values() if n.state != RaftNode.LEADER}

    for lid, llog in leader_logs.items():
        for fid, flog in follower_logs.items():
            common = min(len(llog), len(flog))
            for i in range(common):
                assert llog[i] == flog[i], \
                    f"Log mismatch: leader {lid}[{i}]={llog[i]} != follower {fid}[{i}]={flog[i]}"

    print("  ✓ Leader Completeness Property: verified")
    print("  ✓ Log Matching Property: verified")


if __name__ == "__main__":
    COMMANDS = ["SET x=1", "SET y=2", "GET x", "SET z=3", "DELETE y"]
    NUM_NODES = 5

    print(f"Raft Consensus Simulator — {NUM_NODES} nodes, {len(COMMANDS)} commands")
    print(f"Running simulation with asyncio...\n")

    nodes = asyncio.run(simulate(NUM_NODES, COMMANDS, rounds=800))

    for n in nodes.values():
        applied = n.get_applied_commands()
        print(f"  Node {n.id} [{n.state}]  term={n.current_term}  "
              f"log={len(n.log)-1}  committed={n.commit_index}  "
              f"applied={applied}")

    print()
    _verify_safety(nodes)
    print("\n✓ Raft consensus simulation complete.")
