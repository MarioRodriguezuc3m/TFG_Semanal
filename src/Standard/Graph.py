from typing import List, Dict, Tuple, Set
from collections import defaultdict
from utils.Ant import Ant

class Graph:
    def __init__(self, nodes: List[Tuple], edges: Dict[Tuple, List[Tuple]], initial_pheromone: float = 1.0):
        self.nodes = nodes
        self.edges = edges
        self.initial_pheromone = initial_pheromone # El valor original de inicio
        self.current_base_pheromone = initial_pheromone # El nivel base que decae
        self.pheromone: Dict[Tuple[Tuple, Tuple], float] = {} 
        print("Graph initialized with nodes and edges.")

    def get_pheromone(self, node1: Tuple, node2: Tuple) -> float:
        """Obtiene el nivel de feromona entre dos nodos."""
        # Si la arista tiene un valor explícito, se devuelve.
        # De lo contrario, se devuelve el nivel base actual de feromona.
        edge = (node1, node2)
        return self.pheromone.get(edge, self.current_base_pheromone)

    def update_pheromone(self, ants: List['Ant'], rho: float, Q: float):
        """Actualiza las feromonas del grafo en base a las soluciones de la lista de hormigas que recibe como parámetro."""
    # 1. Evaporación global (actualiza current_base_pheromone y las explícitas)
        self.current_base_pheromone *= (1 - rho)
        
        for edge_key in list(self.pheromone.keys()): # Evaporación de feromonas explícitas
            self.pheromone[edge_key] *= (1 - rho)
        # 2. Depósito de feromonas
        for ant in ants:
            if not ant.visited or not hasattr(ant, 'total_cost'):
                continue
            
            if hasattr(ant, 'valid_solution') and ant.valid_solution and ant.total_cost > 0:
                delta = Q / ant.total_cost
            else:
                continue

            for i in range(len(ant.visited) - 1):
                node_from = ant.visited[i]
                node_to = ant.visited[i+1]
                edge = (node_from, node_to)

                # Obtenemos el valor actual de la arista (explícito o el base_pheromone)
                pheromone_before_deposit = self.get_pheromone(node_from, node_to)
                new_explicit_value = pheromone_before_deposit + delta
                
                # Actualizamos la feromona de la arista con el nuevo valor explícito
                self.pheromone[edge] = new_explicit_value