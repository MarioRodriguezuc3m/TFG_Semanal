from Standard.ACO import ACO
from MinMax.MinMaxGraph import MinMaxGraph
from utils.Ant import Ant
from typing import List, Dict
import matplotlib.pyplot as plt
import time
import os

class MinMaxACO(ACO):
    def __init__(self,
                 graph: MinMaxGraph, 
                 config_data: Dict,        
                 horas_disponibles: List[str],
                 n_ants: int = 10,
                 iterations: int = 100,
                 alpha: float = 1.0,
                 beta: float = 3.0,
                 rho: float = 0.1,
                 Q: float = 1.0):

        super().__init__(graph=graph,
                         config_data=config_data,
                         horas_disponibles=horas_disponibles,
                         n_ants=n_ants,
                         iterations=iterations,
                         alpha=alpha,
                         beta=beta,
                         rho=rho,
                         Q=Q)

        self.graph: MinMaxGraph = graph

    def run(self):
        start_time = time.time()

        for iteration_num in range(self.iterations):
            ants = [Ant(graph=self.graph,
                        paciente_to_estudio_info=self.paciente_to_estudio,
                        pacientes=self.pacientes,
                        duracion_consultas=self.duracion_consultas,
                        alpha=self.alpha,
                        beta=self.beta)
                    for _ in range(self.n_ants)]

            iteration_best_ant_obj = None
            iteration_best_cost = float('inf')

            # Calcular pasos máximos para evitar bucles infinitos
            max_steps_for_ant = 0
            if self.pacientes and self.paciente_to_estudio:
                max_steps_for_ant = sum(len(info["fases"]) for p, info in self.paciente_to_estudio.items() if p in self.pacientes) * 2
            if max_steps_for_ant == 0 and self.pacientes:
                max_steps_for_ant = len(self.pacientes) * 10

            # Construcción de soluciones
            for ant in ants:
                steps = 0
                while steps < max_steps_for_ant:
                    next_node = ant.choose_next_node()
                    if next_node is None or ant.valid_solution:
                        break
                    ant.move(next_node)
                    steps += 1

                if ant.valid_solution:
                    cost = self.calcular_coste(ant.visited)
                    ant.total_cost = cost
                    if cost < iteration_best_cost:
                        iteration_best_ant_obj = ant
                        iteration_best_cost = cost
            
            # Búsqueda local y actualización del mejor global
            ant_for_pheromone_update = iteration_best_ant_obj

            if iteration_best_ant_obj:
                # Aplicar búsqueda local a la mejor solución de la iteración
                ls_solution = self.local_search(iteration_best_ant_obj.visited)
                ls_cost = self.calcular_coste(ls_solution)

                # Si la búsqueda local mejoró la solución, usarla para actualizar feromonas
                if ls_cost < iteration_best_cost:
                    iteration_best_cost = ls_cost
                    temp_ls_ant = Ant(graph=self.graph,
                                      paciente_to_estudio_info=self.paciente_to_estudio,
                                      pacientes=self.pacientes,
                                      duracion_consultas=self.duracion_consultas,
                                      alpha=self.alpha, beta=self.beta)
                    temp_ls_ant.visited = ls_solution
                    temp_ls_ant.total_cost = ls_cost
                    temp_ls_ant.valid_solution = True
                    ant_for_pheromone_update = temp_ls_ant
                
                # Actualizar mejor solución global si es necesario
                if iteration_best_cost < self.best_cost:
                    self.best_cost = iteration_best_cost
                    if ant_for_pheromone_update == [iteration_best_ant_obj]:
                        self.best_solution = iteration_best_ant_obj.visited.copy()
                    else:
                        self.best_solution = ls_solution.copy()

            # Actualizar feromonas usando el método de MinMaxGraph
            if not ant_for_pheromone_update:
                self.graph.update_pheromone(
                    best_ant=[],  # No hay mejor hormiga para actualizar
                    rho=self.rho,
                    Q=self.Q
                )
            else:
                self.graph.update_pheromone(
                    best_ant=ant_for_pheromone_update,
                    rho=self.rho,
                    Q=self.Q
                )

            # Registrar el mejor costo para gráfica de convergencia
            cost_to_log = float('inf')
            if self.best_cost != float('inf'):
                cost_to_log = self.best_cost
            elif iteration_best_cost != float('inf') and ant_for_pheromone_update:
                 cost_to_log = iteration_best_cost
            elif self.total_costs:
                cost_to_log = self.total_costs[-1]
            
            self.total_costs.append(cost_to_log)

            if iteration_num % 10 == 0:  # Reducir frecuencia de prints
                print(f"Iteración {iteration_num}/{self.iterations} - Mejor: {self.best_cost:.2f}")

        self.execution_time = time.time() - start_time
        return self.best_solution, self.best_cost

    def plot_convergence(self):
        if not self.total_costs or all(c == float('inf') for c in self.total_costs):
            print("No hay datos válidos para la gráfica de convergencia.")
            return

        # Filtrar valores infinitos para graficar
        plot_costs = [c for c in self.total_costs if c != float('inf')]
        if not plot_costs and self.total_costs:
            if self.best_cost != float('inf'):
                plot_costs = [self.best_cost] * len(self.total_costs)
            else:
                print("Todos los costos son infinitos. No se puede graficar.")
                return

        plt.figure(figsize=(10, 6))
        plt.plot(plot_costs, marker='o', linestyle='-')
        plt.xlabel('Iteración')
        plt.ylabel('Mejor Costo')
        plt.title('Convergencia Min-Max ACO')
        plt.grid(True)

        plot_dir = "/app/plots"
        os.makedirs(plot_dir, exist_ok=True)

        try:
            filepath = os.path.join(plot_dir, "convergencia_MinMaxACO.png")
            plt.savefig(filepath)
            print(f"Gráfica guardada en {filepath}")
        except Exception as e:
            print(f"Error al guardar gráfica: {e}")
        plt.close()