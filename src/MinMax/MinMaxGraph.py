from Standard.Graph import Graph
from utils.Ant import Ant
from typing import List, Dict, Tuple, Optional

class MinMaxGraph(Graph):
    def __init__(self,
                 nodes: List[Tuple],
                 edges: Dict[Tuple, List[Tuple]],
                 pheromone_max: float = 10.0,  
                 pheromone_min: float = 0.1,   
                 initial_pheromone: Optional[float] = None):
        
        # Asegurar que initial_pheromone no sea None y respete los límites
        effective_initial_pheromone = initial_pheromone if initial_pheromone is not None else pheromone_max

        super().__init__(nodes, edges, initial_pheromone=effective_initial_pheromone)

        self.pheromone_max = pheromone_max
        self.pheromone_min = pheromone_min

        # Asegurar que la feromona base inicial también respeta los límites
        # y las feromonas explícitas si la clase base las inicializa
        if hasattr(self, 'current_base_pheromone'):
            self.current_base_pheromone = max(self.pheromone_min, self.current_base_pheromone)
            self.current_base_pheromone = min(self.pheromone_max, self.current_base_pheromone)
        
        for edge_key in self.pheromone: # self.pheromone es el dict de la clase base
            current_val = self.pheromone[edge_key]
            self.pheromone[edge_key] = min(max(current_val, self.pheromone_min), self.pheromone_max)


    def update_pheromone(self, ants: List['Ant'], rho: float, Q: float):
        """
        Actualiza las feromonas usando la lógica de la clase base Graph
        y luego aplica los límites Min-Max.
        """
        # 1. Dejar que la clase base haga la evaporación y el depósito de feromonas
        super().update_pheromone(ants=ants, rho=rho, Q=Q)

        # 2. Aplicar los límites Min-Max a todas las feromonas después de la actualización.
        if hasattr(self, 'current_base_pheromone'):
            self.current_base_pheromone = max(self.pheromone_min, self.current_base_pheromone)
            self.current_base_pheromone = min(self.pheromone_max, self.current_base_pheromone)

        # Aplicar límites a todas las feromonas explícitas en el diccionario self.pheromone
        for edge_key in self.pheromone: # self.pheromone es el dict de la clase base
            current_val = self.pheromone[edge_key]
            self.pheromone[edge_key] = min(max(current_val, self.pheromone_min), self.pheromone_max)
