"""
IEM Capable Mixin for Message-Driven Nodes

Clean, generic packet handling with minimal interface.
Handles transport layer generically, delegates business logic to packet handlers.
"""

import logging
from typing import Any, TypeVar, Generic, List
from global_utils.utils.logging_config import emit
from mas.graph.state.state_view import StateView
from mas.graph.state.graph_state import Channel
from mas.core.iem.packets import BaseIEMPacket, TaskPacket
from mas.core.iem.models import PacketType, ElementAddress
from mas.core.iem.interfaces import InterMessenger
from mas.core.iem.factory import messenger_from_ctx
from mas.core.contracts import SupportsStateContext
from mas.core.iem.utils import get_outgoing_targets

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Type variable bound to the minimal "SupportsStateContext" Protocol.
# TSupportsState represents any class that implements state/context interface:
#  - |get_state() -> StateView
#  - |get_context() -> StepContext
# This ensures static type checkers know `self` has state/context capability.
# -----------------------------------------------------------------------------
TSupportsState = TypeVar("TSupportsState", bound=SupportsStateContext)


class IEMCapableMixin(Generic[TSupportsState]):
    """
    Mixin for nodes that use the IEM protocol.
    
    Clean, generic packet handling:
    - Transport layer: routing, acknowledgment, lifecycle
    - Business layer: delegates to packet type handlers
    
    SOLID principles:
    - Single Responsibility: Only handles packet transport
    - Open/Closed: Extensible via packet type handlers
    - Dependency Inversion: Depends on InterMessenger abstraction
    """

    # Channel permissions (inherited by MRO)
    MIXIN_READS = {Channel.INTER_PACKETS}
    MIXIN_WRITES = {Channel.INTER_PACKETS}

    def __init_subclass__(cls) -> None:
        """Ensure the concrete class implements required protocols."""
        if not issubclass(cls, SupportsStateContext):
            raise TypeError(
                f"{cls.__name__} requires state/context support (get_state() + get_context())."
            )
        super().__init_subclass__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_messenger(self: TSupportsState) -> InterMessenger:
        """
        Get IEM messenger bound to current state.
        
        Factory method that creates a fresh messenger with current state.
        Ensures messenger always works with up-to-date state.
        
        Returns:
            InterMessenger configured for this node
            
        Raises:
            RuntimeError: If called outside of node execution
        """
        try:
            state = self.get_state()
            context = self.get_context()
        except RuntimeError:
            raise RuntimeError("IEM messenger not available outside of run()")

        return messenger_from_ctx(state, context)

    @property
    def ms(self: TSupportsState) -> InterMessenger:
        """Access to IEM messenger - creates fresh instance with current state."""
        return self.get_messenger()

    @property
    def messenger(self: TSupportsState) -> InterMessenger:
        """Alias for ms property."""
        return self.ms

    # === GENERIC PACKET OPERATIONS ===
    def send_packet(self, packet: BaseIEMPacket) -> str:
        """
        Send any packet via IEM.
        
        Args:
            packet: Packet to send
            
        Returns:
            Packet ID for tracking
        """
        return self.ms.send_packet(packet)

    def broadcast_packet(self, packet: BaseIEMPacket) -> List[str]:
        """
        Broadcast packet to all adjacent nodes.
        
        Args:
            packet: Packet to broadcast
            
        Returns:
            List of packet IDs sent
        """
        return self.ms.broadcast_packet(packet)

    def multicast_packet(self, packet: BaseIEMPacket, target_uids: List[str]) -> List[str]:
        """
        Send packet to multiple specific nodes (multicast).
        
        Args:
            packet: Packet to send
            target_uids: Specific target node UIDs
            
        Returns:
            List of packet IDs sent
        """
        return self.ms.multicast_packet(packet, target_uids)

    def reply_packet(self, original_packet: BaseIEMPacket, reply_packet: BaseIEMPacket) -> str:
        """
        Reply to packet with another packet.
        
        Args:
            original_packet: Original packet to reply to
            reply_packet: Reply packet to send
            
        Returns:
            Reply packet ID
        """
        reply_packet.dst = original_packet.src
        return self.send_packet(reply_packet)

    def inbox_packets(self, packet_type: PacketType = None) -> List[BaseIEMPacket]:
        """
        Get incoming packets, optionally filtered by type.
        
        Args:
            packet_type: Filter by packet type, or None for all
            
        Returns:
            List of matching packets
        """
        return self.ms.inbox_packets(packet_type)

    def process_packets(self, state: StateView) -> None:
        """
        Process all incoming packets.
        
        Handles acknowledgment and delegates to packet type handlers.
        """
        for packet in self.inbox_packets():
            try:
                self.handle_packet(packet)
            finally:
                self.acknowledge(packet.id)

    def handle_packet(self, packet: BaseIEMPacket) -> None:
        """
        Handle incoming packet based on type.
        
        Delegates to specific packet type handlers.
        Override packet type handlers in subclasses.
        
        Args:
            packet: Packet to handle
        """
        if packet.type == PacketType.TASK:
            self.handle_task_packet(packet)
        elif packet.type == PacketType.SYSTEM:
            self.handle_system_packet(packet)
        elif packet.type == PacketType.DEBUG:
            self.handle_debug_packet(packet)
        else:
            emit(logger, logging.WARNING, "iem.unknown_packet_type", packet_type=packet.type)

    # === PACKET TYPE HANDLERS (Override in subclasses) ===
    def handle_task_packet(self, packet: BaseIEMPacket) -> None:
        """
        Override to handle task packets.
        
        Args:
            packet: Task packet to handle
        """
        pass

    def handle_system_packet(self, packet: BaseIEMPacket) -> None:
        """
        Override to handle system packets.
        
        Args:
            packet: System packet to handle
        """
        pass

    def handle_debug_packet(self, packet: BaseIEMPacket) -> None:
        """
        Override to handle debug packets.
        
        Args:
            packet: Debug packet to handle
        """
        pass

    # === TASK OPERATIONS ===
    def send_task(self: TSupportsState, dst: str, task: 'Task') -> str:
        """
        Send task to specific node.
        
        Args:
            dst: Destination node UID
            task: Task to send
            
        Returns:
            Packet ID for tracking
        """
        packet = TaskPacket.create(
            src=ElementAddress(uid=self.get_context().uid),
            dst=ElementAddress(uid=dst),
            task=task
        )
        return self.send_packet(packet)

    def broadcast_task(self: TSupportsState, task: 'Task') -> List[str]:
        """
        Broadcast task to all adjacent nodes.
        
        Args:
            task: Task to broadcast
            
        Returns:
            List of packet IDs sent
        """
        packet = TaskPacket.create(
            src=ElementAddress(uid=self.get_context().uid),
            dst=ElementAddress(uid=""),  # Will be overridden in broadcast
            task=task
        )
        return self.broadcast_packet(packet)

    def multicast_task(self: TSupportsState, task: 'Task', target_uids: List[str]) -> List[str]:
        """
        Send task to multiple specific nodes (multicast).
        
        Args:
            task: Task to send
            target_uids: Specific target node UIDs
            
        Returns:
            List of packet IDs sent
        """
        packet = TaskPacket.create(
            src=ElementAddress(uid=self.get_context().uid),
            dst=ElementAddress(uid=""),  # Will be overridden in multicast
            task=task
        )
        return self.multicast_packet(packet, target_uids)

    def reply_task(self: TSupportsState, original_packet: BaseIEMPacket, response_task: 'Task') -> str:
        """
        Reply to packet with task.
        
        Args:
            original_packet: Original packet to reply to
            response_task: Task to send as response
            
        Returns:
            Reply packet ID
        """
        reply_packet = TaskPacket.create(
            src=ElementAddress(uid=self.get_context().uid),
            dst=original_packet.src,
            task=response_task
        )
        return self.send_packet(reply_packet)

    # === UTILITIES ===
    def acknowledge(self, packet_id: str) -> bool:
        """Acknowledge packet. Delegates to messenger."""
        return self.ms.acknowledge(packet_id)

    def purge(self, **kwargs) -> int:
        """Purge old packets from state. Delegates to messenger."""
        return self.ms.purge(**kwargs)

    def has_outgoing_packets(self: TSupportsState) -> bool:
        """
        Check if this node has sent unacknowledged packets to adjacent nodes.
        
        Useful for routing decisions - determines if node should wait for
        responses via router path vs. going to finalization path.
        
        Returns:
            True if there are outgoing packets to adjacent nodes, False otherwise
            
        Example:
            # In orchestrator batch processing:
            if final_result:
                if status.is_complete or not self.has_outgoing_packets():
                    self._finalize_completed_work(thread_id, final_result)
        """
        try:
            state = self.get_state()
            context = self.get_context()
            targets = get_outgoing_targets(state, context)
            return len(targets) > 0
        except RuntimeError:
            # Called outside of run() - no packets can exist
            return False

    def get_outgoing_targets(self: TSupportsState) -> set[str]:
        """
        Get UIDs of adjacent nodes that have unacknowledged packets from this node.
        
        More detailed than has_outgoing_packets() - returns actual target UIDs.
        Useful for debugging or conditional logic based on specific targets.
        
        Returns:
            Set of adjacent node UIDs with pending packets, empty set if none
            
        Example:
            # Check if specific node has pending work
            targets = self.get_outgoing_targets()
            if 'jira_agent' in targets:
                print("Still waiting for Jira agent response")
        """
        try:
            state = self.get_state()
            context = self.get_context()
            return get_outgoing_targets(state, context)
        except RuntimeError:
            # Called outside of run() - return empty set
            return set()
