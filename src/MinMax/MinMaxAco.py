from Standard.ACO import ACO
from MinMax.MinMaxGraph import MinMaxGraph
from utils.Ant import Ant
from typing import List, Dict
import matplotlib.pyplot as plt
import time
import os
from collections import defaultdict

class MinMaxACO(ACO):
    def __init__(self,
                 graph: MinMaxGraph,
                 config_data: Dict,        
                 horas_disponibles: List[str], # Para un día tipo
                 num_dias_planificacion: int,
                 lista_personal_instancias: List[str] = None,
                 n_ants: int = 10,
                 iterations: int = 100,
                 alpha: float = 1.0,
                 beta: float = 3.0,
                 rho: float = 0.1, # Tasa de evaporación y aprendizaje
                 Q: float = 1.0):  # Factor de depósito de feromona

        # Inicialización de atributos igual que en ACO principal
        super().__init__(
            graph=graph,
            config_data=config_data,
            horas_disponibles=horas_disponibles,
            num_dias_planificacion=num_dias_planificacion,
            lista_personal_instancias=lista_personal_instancias,
            n_ants=n_ants,
            iterations=iterations,
            alpha=alpha,
            beta=beta,
            rho=rho,
            Q=Q
        )
        self.graph: MinMaxGraph

        # Atributos adicionales para compatibilidad
        self.max_fases_por_dia_paciente = config_data.get("max_fases_por_dia_paciente", 2)
        self.fase_a_roles_compatibles = defaultdict(list)
        self.cargos_config = config_data["cargos"]
        for rol, fases_asignadas in self.cargos_config.items():
            for fase in fases_asignadas:
                self.fase_a_roles_compatibles[fase].append(rol)
        self.consultas = config_data["consultas"]

    def run(self):
        """
        Ejecuta el algoritmo Min-Max Ant System.
        """
        start_time = time.time()
        self.total_costs = []
        self.best_cost = float('inf')
        self.best_solution = None

        for iteration in range(self.iterations):
            # Crear las hormigas para esta iteración
            ants = [Ant(self.graph, self.paciente_to_estudio, self.pacientes, 
                        self.duracion_consultas, self.num_dias_planificacion, 
                        self.alpha, self.beta, self.max_fases_por_dia_paciente) for _ in range(self.n_ants)]
            
            iteration_best_cost = float('inf')
            iteration_best_solution_path = None 
            iteration_best_ant_object = None 

            # Calcular el máximo de pasos permitidos para evitar bucles infinitos
            max_steps = sum(len(self.paciente_to_estudio[p]["orden_fases"]) for p in self.pacientes) * 2 # Usar orden_fases
            if max_steps == 0: max_steps = 20 * self.num_dias_planificacion

            for ant in ants:
                # Reiniciar el estado interno de la hormiga
                ant.visited = []
                ant.pacientes_progreso.clear()
                ant.paciente_dia_fase_contador.clear()
                ant.current_node = None
                ant.valid_solution = False

                steps = 0
                # Construcción de la solución por la hormiga
                while steps < max_steps and not ant.valid_solution:
                    next_node = ant.choose_next_node()
                    if next_node is None:
                        break
                    ant.move(next_node)
                    steps += 1
                
                # Si la hormiga encuentra una solución válida, calcular su coste
                if ant.valid_solution:
                    cost = self.calcular_coste(ant.visited)
                    ant.total_cost = cost
                    
                    # Actualizar la mejor solución de la iteración si corresponde
                    if cost < iteration_best_cost:
                        iteration_best_cost = cost
                        iteration_best_solution_path = ant.visited.copy()
                        iteration_best_ant_object = ant

            ant_to_update_pheromone_with = None

            if iteration_best_solution_path is not None:
                # Aplicar búsqueda local a la mejor solución de la iteración
                ls_solution = self.local_search(iteration_best_solution_path)
                ls_cost = self.calcular_coste(ls_solution)

                # Si la búsqueda local mejora la solución, actualizar
                if ls_cost < iteration_best_cost:
                    iteration_best_cost = ls_cost
                    iteration_best_solution_path = ls_solution 

                    temp_ls_ant = Ant(self.graph, self.paciente_to_estudio, self.pacientes,
                                        self.duracion_consultas, self.num_dias_planificacion,
                                        self.alpha, self.beta, self.max_fases_por_dia_paciente)
                    temp_ls_ant.visited = ls_solution
                    temp_ls_ant.total_cost = ls_cost
                    temp_ls_ant.valid_solution = True 
                    iteration_best_ant_object = temp_ls_ant 
                
                # Actualizar la mejor solución global si corresponde
                if iteration_best_cost < self.best_cost:
                    self.best_cost = iteration_best_cost
                    self.best_solution = iteration_best_solution_path.copy()
                
                # La hormiga que se usará para actualizar las feromonas será la mejor de la iteración
                ant_to_update_pheromone_with = iteration_best_ant_object

            # Se prepara la mejor hormiga de la iteración para actualizar las feromonas
            ants_for_update_list = []
            if ant_to_update_pheromone_with:
                ants_for_update_list.append(ant_to_update_pheromone_with)
            
            # Actualizar feromonas en el grafo
            self.graph.update_pheromone(ants=ants_for_update_list, rho=self.rho, Q=self.Q)

            # Registrar el coste para la gráfica de convergencia
            cost_to_log = self.best_cost if self.best_cost != float('inf') else \
                          (iteration_best_cost if iteration_best_cost != float('inf') else \
                          (self.total_costs[-1] if self.total_costs and self.total_costs[-1] != float('inf') else float('inf')))
            self.total_costs.append(cost_to_log)

            # Mostrar progreso cada 10 iteraciones
            if iteration % 10 == 0:
                current_best_display = f"{self.best_cost:.2f}" if self.best_cost != float('inf') else "N/A"
                print(f"Iteración {iteration}/{self.iterations} - Mejor Costo Global (MinMax): {current_best_display}")

        end_time = time.time()
        self.execution_time = end_time - start_time
        return self.best_solution, self.best_cost

    def plot_convergence(self, output_dir: str = "/plots"):
        """
        Genera y guarda un gráfico de la convergencia del algoritmo ACO.
        """
        if not self.total_costs:
            print("No hay datos para graficar convergencia.")
            return

        plt.figure(figsize=(10, 6))
        plt.plot(self.total_costs, marker='o', linestyle='-')
        plt.xlabel('Iteración')
        plt.ylabel('Mejor Costo Encontrado')
        plt.title('Convergencia del Algoritmo ACO')
        plt.grid(True)

        if not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        try:
            plt.savefig(os.path.join(output_dir, "convergencia_MinMax_aco.png"))
            print(f"Gráfico guardado en {os.path.join(output_dir, 'convergencia_MinMax_aco.png')}")
        except Exception as e:
            print(f"Error guardando gráfico: {e}")
        plt.close()
