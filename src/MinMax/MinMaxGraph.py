from utils.Ant import Ant
from Standard.Graph import Graph
from typing import List, Dict, Tuple, Optional

class MinMaxGraph(Graph):
    def __init__(self,
                 nodes: List[Tuple],
                 edges: Dict[Tuple, List[Tuple]],
                 pheromone_max: float = 100.0,  # tau_max
                 pheromone_min: float = 0.1,    # tau_min
                 initial_pheromone_value: Optional[float] = None): # Este puede ser ignorado o usado para tau_max

        init_pher_val_for_super = pheromone_max 

        super().__init__(nodes, edges, initial_pheromone=init_pher_val_for_super)

        self.pheromone_max = pheromone_max
        self.pheromone_min = pheromone_min


    def update_pheromone(self, best_ant: Optional[Ant], rho: float, Q: float):
        ants_for_super_update: List[Ant] = []
        if best_ant and best_ant.valid_solution and best_ant.total_cost > 0:
            ants_for_super_update.append(best_ant)
        
        # Llamar al método de actualización de feromonas de la superclase
        super().update_pheromone(ants=ants_for_super_update, rho=rho, Q=Q)

        # Aplicar los límites Min-Max a todas las feromonas gestionadas.
        if hasattr(self, 'current_base_pheromone'): # Debería existir por la herencia
            self.current_base_pheromone = max(self.pheromone_min, self.current_base_pheromone)
            self.current_base_pheromone = min(self.pheromone_max, self.current_base_pheromone)

        #Aplicar límites a todas las feromonas explícitas en el diccionario self.pheromone
        for edge in list(self.pheromone.keys()): # Iterar sobre una copia de las claves
            current_val = self.pheromone[edge]
            limited_val = max(self.pheromone_min, current_val)
            limited_val = min(self.pheromone_max, limited_val)
            self.pheromone[edge] = limited_val
