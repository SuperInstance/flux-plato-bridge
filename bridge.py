#!/usr/bin/env python3
"""
flux-plato-bridge — Connect FLUX bytecode execution to PLATO knowledge tiles
Translate between FLUX VM state and PLATO tile operations.

The bridge enables:
- FLUX agents to read/write PLATO tiles as native operations
- PLATO tiles to trigger FLUX bytecode execution
- Bidirectional sync between computation and knowledge

Usage:
    from flux_plato_bridge import FluxPlatoBridge
    
    bridge = FluxPlatoBridge()
    
    # FLUX agent reads PLATO tile
    tile = bridge.read_tile(room="fleet_orchestration", tile_id=42)
    
    # FLUX agent writes PLATO tile
    bridge.write_tile(room="knowledge", question="Fleet status?", answer="All green")
    
    # PLATO tile triggers FLUX execution
    result = bridge.execute_from_tile(tile)
"""

import json, time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class TileContext:
    room: str
    tile_id: int
    question: str
    answer: str
    agent: str
    timestamp: float

class FluxPlatoBridge:
    """Bridge between FLUX VM and PLATO knowledge lattice."""
    
    def __init__(self, plato_url: str = "http://147.224.38.131:8847"):
        self.plato_url = plato_url
        self.tile_cache: Dict[str, TileContext] = {}
        self.execution_log: List[Dict] = []
        self.bytecode_buffer: List[int] = []
    
    def read_tile(self, room: str, tile_id: int) -> Optional[TileContext]:
        """Read a PLATO tile into FLUX context."""
        cache_key = f"{room}:{tile_id}"
        
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.plato_url}/rooms/{room}/tiles/{tile_id}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                tile = TileContext(
                    room=room,
                    tile_id=tile_id,
                    question=data.get("question", ""),
                    answer=data.get("answer", ""),
                    agent=data.get("agent", "unknown"),
                    timestamp=data.get("timestamp", time.time())
                )
                self.tile_cache[cache_key] = tile
                return tile
        except Exception as e:
            # Fallback to cache
            if cache_key in self.tile_cache:
                return self.tile_cache[cache_key]
            return None
    
    def write_tile(self, room: str, question: str, answer: str, agent: str = "flux-bridge") -> bool:
        """Write a FLUX computation result as PLATO tile."""
        try:
            import urllib.request
            data = json.dumps({
                "question": question,
                "answer": answer,
                "agent": agent,
                "room": room
            }).encode()
            
            req = urllib.request.Request(
                f"{self.plato_url}/submit",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception as e:
            self.execution_log.append({
                "action": "write_tile",
                "error": str(e),
                "time": time.time()
            })
            return False
    
    def tile_to_bytecode(self, tile: TileContext) -> bytes:
        """Convert a PLATO tile to FLUX bytecode sequence."""
        from flux_isa import ISAEncoder
        enc = ISAEncoder()
        
        bytecode = b""
        
        # Encode tile metadata as immediate values
        # R0 = room_id (hash of room name)
        room_hash = hash(tile.room) & 0xFFFF
        bytecode += enc.movi(0, room_hash)
        
        # R1 = tile_id
        bytecode += enc.movi(1, tile.tile_id & 0xFFFF)
        
        # R2 = agent_id (hash)
        agent_hash = hash(tile.agent) & 0xFFFF
        bytecode += enc.movi(2, agent_hash)
        
        # Push question length hint
        q_len = len(tile.question) & 0xFFFF
        bytecode += enc.movi(3, q_len)
        
        # Push answer length hint
        a_len = len(tile.answer) & 0xFFFF
        bytecode += enc.movi(4, a_len)
        
        # PLATO_WRITE operation
        bytecode += enc.plato_write(room_hash & 0xFF, 4)
        
        return bytecode
    
    def execute_from_tile(self, tile: TileContext) -> Dict:
        """Execute FLUX bytecode derived from a PLATO tile."""
        from flux_isa import FluxVM
        
        bytecode = self.tile_to_bytecode(tile)
        
        vm = FluxVM()
        vm.load(bytecode)
        steps = vm.run(max_steps=100)
        
        result = {
            "tile": tile,
            "steps_executed": steps,
            "vm_state": vm.get_state(),
            "tiles_submitted": vm.tiles_submitted
        }
        
        self.execution_log.append(result)
        return result
    
    def search_and_execute(self, room: str, query: str) -> List[Dict]:
        """Search PLATO room, execute FLUX on matching tiles."""
        # For demo: simulate search by returning cached tiles
        results = []
        for key, tile in self.tile_cache.items():
            if tile.room == room and query.lower() in (tile.question + tile.answer).lower():
                result = self.execute_from_tile(tile)
                results.append(result)
        return results
    
    def get_bridge_stats(self) -> Dict:
        return {
            "cache_size": len(self.tile_cache),
            "execution_count": len(self.execution_log),
            "plato_url": self.plato_url
        }
    
    def sync_status(self) -> bool:
        """Check if PLATO gate is reachable."""
        try:
            import urllib.request
            urllib.request.urlopen(self.plato_url + "/status", timeout=3)
            return True
        except:
            return False

def demo():
    print("=== FLUX↔PLATO Bridge Demo ===\n")
    
    bridge = FluxPlatoBridge()
    
    # Create a sample tile
    tile = TileContext(
        room="knowledge",
        tile_id=1,
        question="What is the fleet status?",
        answer="10 services up, 2 vessels active",
        agent="oracle1",
        timestamp=time.time()
    )
    
    print("1. Tile-to-Bytecode Translation:")
    bytecode = bridge.tile_to_bytecode(tile)
    print(f"   Generated {len(bytecode)} bytes of FLUX bytecode")
    
    print("\n2. Bytecode Disassembly:")
    from flux_isa import ISADecoder
    decoder = ISADecoder()
    for line in decoder.disassemble(bytecode):
        print(f"   {line}")
    
    print("\n3. Execute from Tile:")
    result = bridge.execute_from_tile(tile)
    print(f"   Steps: {result['steps_executed']}")
    print(f"   VM state: {result['vm_state']}")
    
    print("\n4. Bridge Stats:")
    print(f"   {bridge.get_bridge_stats()}")
    
    print("\n5. PLATO Sync Check:")
    reachable = bridge.sync_status()
    print(f"   PLATO reachable: {reachable}")
    
    if reachable:
        print("\n6. Write Tile to PLATO:")
        ok = bridge.write_tile("flux_bridge", "FLUX execution result", "Completed 5 steps")
        print(f"   Write success: {ok}")

if __name__ == "__main__":
    demo()
