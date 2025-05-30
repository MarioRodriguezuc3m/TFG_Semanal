import matplotlib.pyplot as plt 
from utils.Ant import Ant
from typing import Dict, List, Tuple
from collections import defaultdict
import datetime
import random
import time 
import os
import math
try:
    from Standard.Graph import Graph
except ImportError:
    pass


class ACO:
    def __init__(self, graph: Graph, config_data: Dict, horas_disponibles: List, n_ants: int = 10, iterations: int = 100,
                 alpha: float = 1.0, beta: float = 3.0, rho: float = 0.1, Q: float = 1.0):
        self.graph = graph
        self.config_data = config_data
        
        self.tipos_estudio = config_data["tipos_estudio"]
        self.consultas = config_data["consultas"]
        self.horas = horas_disponibles
        self.duracion_consultas = config_data.get("intervalo_consultas_minutos")
        self.medicos = config_data["medicos"]
        
        self.paciente_to_estudio = {} 
        _unique_pacientes_set = set()

        for estudio in self.tipos_estudio:
            for paciente in estudio["pacientes"]:
                _unique_pacientes_set.add(paciente)
                self.paciente_to_estudio[paciente] = {
                    "nombre_estudio": estudio["nombre_estudio"],
                    "fases": estudio["fases"], 
                    "orden_fases": estudio["orden_fases"],
                }
        self.pacientes = list(_unique_pacientes_set)
        
        self.n_ants = n_ants
        self.iterations = iterations
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.Q = Q
        self.best_solution = None
        self.total_costs = [] 
        self.best_cost = float('inf')
        self.execution_time = None

    def run(self):
        start_time = time.time()
        
        for iteration in range(self.iterations):
            ants = [Ant(self.graph, self.paciente_to_estudio, self.pacientes,self.duracion_consultas,
                        self.alpha, self.beta) for _ in range(self.n_ants)]
            
            iteration_best_cost = float('inf')
            iteration_best_solution = None

            active_ants_solutions = []

            for ant_idx, ant in enumerate(ants):
                # Límite de pasos para evitar bucles infinitos
                max_steps = sum(len(self.paciente_to_estudio[p]["fases"]) for p in self.pacientes) * 2
                
                steps = 0
                while steps < max_steps and not ant.valid_solution:
                    next_node = ant.choose_next_node()
                    if next_node is None:
                        break 
                    ant.move(next_node)
                    steps += 1
                
                if ant.valid_solution:
                    cost = self.calcular_coste(ant.visited)
                    ant.total_cost = cost
                    active_ants_solutions.append({'ant': ant, 'cost': cost, 'solution': ant.visited.copy()})
                    
                    if cost < iteration_best_cost:
                        iteration_best_cost = cost
                        iteration_best_solution = ant.visited.copy()
            
            # Aplicar búsqueda local a la mejor solución de la iteración
            if iteration_best_solution is not None:
                current_solution_for_ls = iteration_best_solution
                current_cost_for_ls = iteration_best_cost
                
                # Intentar mejoras locales
                for _ in range(3):
                    improved_solution = self.local_search(current_solution_for_ls)
                    improved_cost = self.calcular_coste(improved_solution)
                    
                    if improved_cost < current_cost_for_ls:
                        current_solution_for_ls = improved_solution
                        current_cost_for_ls = improved_cost
                    else:
                        break
                
                # Actualizar si la búsqueda local mejoró
                if current_cost_for_ls < iteration_best_cost:
                    iteration_best_cost = current_cost_for_ls
                    iteration_best_solution = current_solution_for_ls
                
                # Actualizar mejor solución global
                if iteration_best_cost < self.best_cost:
                    self.best_cost = iteration_best_cost
                    self.best_solution = iteration_best_solution.copy()

                if self.best_solution:
                    # Actualizar feromonas con la mejor solución
                    temp_ant_for_pheromone = Ant(self.graph, self.paciente_to_estudio, self.pacientes, self.alpha, self.beta)
                    temp_ant_for_pheromone.visited = self.best_solution
                    temp_ant_for_pheromone.total_cost = self.best_cost
                    self.graph.update_pheromone([temp_ant_for_pheromone], self.rho, self.Q)

            else:
                print(f"Iteración {iteration}: No se encontró solución válida.")
                # Evaporar feromonas si no hay solución válida
                self.graph.update_pheromone([], self.rho, self.Q)

            if iteration % 10 == 0:  # Reducir frecuencia de prints
                print(f"Iteración {iteration}/{self.iterations} - Mejor: {self.best_cost:.2f}")
            self.total_costs.append(self.best_cost if self.best_cost != float('inf') else iteration_best_cost)

        end_time = time.time()
        self.execution_time = end_time - start_time
        
        return self.best_solution, self.best_cost

    def calcular_coste(self, asignaciones: List[Tuple]) -> float:
        """
        Calcula el coste total de una solución evaluando múltiples criterios:
        1. Validez de asignaciones (pacientes, fases, horas, duraciones)
        2. Conflictos de recursos (médicos y consultas ocupados simultáneamente)
        3. Secuencia correcta de fases por paciente
        4. Tiempos de espera entre fases del mismo paciente
        """
        if not asignaciones:
            return float('inf')

        fases_activas_detalle = []
        tiempos_pacientes = defaultdict(list)  # {paciente: [(orden, inicio, fin, fase), ...]}
        hora_str_to_min_cache = {}  # Cache para convertir "HH:MM" a minutos
        
        coste_total = 0.0

        # PASO 1: Validar cada asignación individual
        for asignacion_idx, asignacion in enumerate(asignaciones):
            paciente, consulta, hora_str, medico, fase_nombre = asignacion
            
            # Verificar que el paciente existe en la configuración
            if paciente not in self.paciente_to_estudio:
                coste_total += 50000  # Penalización grave por paciente inexistente
                continue 
            
            estudio_info = self.paciente_to_estudio[paciente]
            
            # Verificar que la fase pertenece al estudio del paciente
            if fase_nombre not in estudio_info["fases"]:
                coste_total += 40000  # Penalización por fase incorrecta
                continue

            # Convertir hora string a minutos (con cache para eficiencia)
            if hora_str not in hora_str_to_min_cache:
                try:
                    hora_obj = datetime.datetime.strptime(hora_str, "%H:%M").time()
                    inicio_min = hora_obj.hour * 60 + hora_obj.minute
                    hora_str_to_min_cache[hora_str] = inicio_min
                except ValueError:
                    coste_total += 60000  # Penalización por formato de hora inválido
                    continue
            else:
                inicio_min = hora_str_to_min_cache[hora_str]
                
            
            fin_min = inicio_min + self.duracion_consultas
            orden_fase = estudio_info["orden_fases"].get(fase_nombre)
            if orden_fase is None:
                coste_total += 46000  # Penalización por orden no definido
                continue

            # Guardar detalles de la fase para análisis posteriores
            fases_activas_detalle.append({
                'paciente': paciente, 'consulta': consulta, 'medico': medico, 'fase': fase_nombre,
                'inicio_min': inicio_min, 'fin_min': fin_min, 'orden': orden_fase,
                'original_tuple': asignacion, 'idx_original': asignacion_idx
            })
            tiempos_pacientes[paciente].append((orden_fase, inicio_min, fin_min, fase_nombre))

        # Si hay errores graves de validación, retornar sin más análisis
        if coste_total > 0:
            return coste_total

        # PASO 2: Detectar conflictos de recursos usando algoritmo de barrido
        eventos = []
        # Crear eventos de inicio y fin para cada fase
        for i, f_activa in enumerate(fases_activas_detalle):
            eventos.append((f_activa['inicio_min'], 'start', i, f_activa['medico'], f_activa['consulta']))
            eventos.append((f_activa['fin_min'], 'end', i, f_activa['medico'], f_activa['consulta']))
        
        eventos.sort()  # Ordenar por tiempo

        medicos_ocupados = defaultdict(int)  # Contador de fases activas por médico
        consultas_ocupadas = defaultdict(int)  # Contador de fases activas por consulta

        # Procesar eventos cronológicamente
        for t, tipo_evento, idx_fase, medico_evento, consulta_evento in eventos:
            if tipo_evento == 'start':
                # Al iniciar una fase, verificar si hay conflicto
                if medicos_ocupados[medico_evento] > 0:
                    coste_total += 2000  # Médico ya ocupado
                medicos_ocupados[medico_evento] += 1
                
                if consultas_ocupadas[consulta_evento] > 0:
                    coste_total += 2000  # Consulta ya ocupada
                consultas_ocupadas[consulta_evento] += 1
            else:  # 'end'
                # Al terminar una fase, liberar recursos
                medicos_ocupados[medico_evento] -= 1
                consultas_ocupadas[consulta_evento] -= 1

        # PASO 3: Verificar secuencia y tiempos por paciente
        for paciente, fases_programadas_paciente in tiempos_pacientes.items():
            estudio_info = self.paciente_to_estudio[paciente]
            fases_programadas_paciente.sort(key=lambda x: x[0])  # Ordenar por orden de fase

            # Verificar que están todas las fases del estudio
            num_fases_definidas = len(estudio_info["orden_fases"])
            if len(fases_programadas_paciente) != num_fases_definidas:
                coste_total += 15000 * abs(num_fases_definidas - len(fases_programadas_paciente))
            
            orden_esperado = 1
            fin_fase_anterior_min = -1

            for orden_actual, inicio_actual_min, fin_actual_min, fase_nombre_actual in fases_programadas_paciente:
                # Verificar que las fases están en el orden correcto
                if orden_actual != orden_esperado:
                    coste_total += 10000  # Penalización por orden incorrecto
                
                if fin_fase_anterior_min != -1:  # No es la primera fase
                    if inicio_actual_min < fin_fase_anterior_min:
                        # Las fases se solapan (imposible para el mismo paciente)
                        coste_total += 5000 * (fin_fase_anterior_min - inicio_actual_min)
                    else:
                        # Calcular tiempo de espera entre fases
                        tiempo_espera = inicio_actual_min - fin_fase_anterior_min
                        if tiempo_espera > 120:  # Más de 2 horas de espera
                            coste_total += (tiempo_espera - 120) * 2  # Penalización creciente
                        elif tiempo_espera > 15:  # Más de 15 minutos
                             coste_total += tiempo_espera * 0.5  # Penalización leve
                
                fin_fase_anterior_min = fin_actual_min
                orden_esperado += 1
        
        return coste_total if coste_total > 0 else 0.1  # Evitar coste cero
        
    def _identificar_asignaciones_conflictivas(self, solution: List[Tuple]) -> List[int]:
        """
        Identifica los índices de las asignaciones en la solución que tienen
        conflictos directos de recursos (médico o consulta ocupados).
        """
        conflictive_indices = set()
        if not solution or len(solution) < 2:
            return []

        # Cache para conversiones de hora y duraciones para eficiencia
        hora_str_to_min_cache = {}
        duracion_consulta_min = self.duracion_consultas  # Asumiendo que tienes esto en self

        # Convertir todas las asignaciones a un formato más manejable con tiempos en minutos
        processed_assignments = []
        for i, asignacion in enumerate(solution):
            paciente, consulta, hora_str, medico, fase = asignacion

            if hora_str not in hora_str_to_min_cache:
                try:
                    hora_obj = datetime.datetime.strptime(hora_str, "%H:%M").time()
                    inicio_min = hora_obj.hour * 60 + hora_obj.minute
                    hora_str_to_min_cache[hora_str] = inicio_min
                except ValueError:
                    continue  # Ignorar asignación con hora inválida
            else:
                inicio_min = hora_str_to_min_cache[hora_str]

            fin_min = inicio_min + duracion_consulta_min
            processed_assignments.append({
                'idx': i, 'paciente': paciente, 'consulta': consulta,
                'medico': medico, 'fase': fase,
                'inicio_min': inicio_min, 'fin_min': fin_min,
                'original_tuple': asignacion
            })

        # Comprobar conflictos entre pares de asignaciones
        for i in range(len(processed_assignments)):
            asig1 = processed_assignments[i]
            for j in range(i + 1, len(processed_assignments)):
                asig2 = processed_assignments[j]

                # Comprobar solapamiento temporal
                overlap = (asig1['inicio_min'] < asig2['fin_min'] and
                        asig2['inicio_min'] < asig1['fin_min'])

                if overlap:
                    # Conflicto de médico (diferentes pacientes, mismo médico)
                    if asig1['medico'] == asig2['medico'] and asig1['paciente'] != asig2['paciente']:
                        conflictive_indices.add(asig1['idx'])
                        conflictive_indices.add(asig2['idx'])

                    # Conflicto de consulta (diferentes pacientes, misma consulta)
                    if asig1['consulta'] == asig2['consulta'] and asig1['paciente'] != asig2['paciente']:
                        conflictive_indices.add(asig1['idx'])
                        conflictive_indices.add(asig2['idx'])

        return list(conflictive_indices)


    def local_search(self, solution: List[Tuple]) -> List[Tuple]:
        current_best_solution = list(solution) # Trabajar con una copia
        current_best_cost = self.calcular_coste(current_best_solution)

        if not current_best_solution or current_best_cost == 0.1:
            return current_best_solution

        num_improvement_attempts = 15 # Limitar intentos

        for attempt in range(num_improvement_attempts):
            if not current_best_solution:
                break
            
            temp_solution = list(current_best_solution) # Copia para modificar en esta iteración de LS

            # 1. Identificar asignaciones conflictivas
            conflictive_indices = self._identificar_asignaciones_conflictivas(temp_solution)
            
            idx_to_change = -1
            if conflictive_indices and random.random() < 0.9: # 90% de probabilidad de elegir un conflicto
                idx_to_change = random.choice(conflictive_indices)
            else: # Sino, o por probabilidad, elegir una aleatoria
                if not temp_solution: continue # Evitar error si temp_solution está vacía
                idx_to_change = random.randrange(len(temp_solution))

            if idx_to_change == -1 or idx_to_change >= len(temp_solution): # Salvaguarda
                continue

            original_assignment = temp_solution[idx_to_change]
            paciente, consulta, hora_str, medico, fase = original_assignment

            # 2. Intentar cambiar un elemento aleatorio de la asignación seleccionada
            change_options = []
            # Cambiar hora
            available_new_horas = [h for h in self.horas if h != hora_str]
            if available_new_horas:
                change_options.append(("hora", random.choice(available_new_horas)))
            
            # Cambiar médico
            available_new_medicos = [m for m in self.medicos if m != medico]
            if available_new_medicos:
                change_options.append(("medico", random.choice(available_new_medicos)))

            # Cambiar consulta
            available_new_consultas = [c for c in self.consultas if c != consulta]
            if available_new_consultas:
                change_options.append(("consulta", random.choice(available_new_consultas)))

            if not change_options:
                continue # No hay opciones de cambio para esta asignación

            change_type, new_value = random.choice(change_options)
            
            new_asig = None
            if change_type == "hora":
                new_asig = (paciente, consulta, new_value, medico, fase)
            elif change_type == "medico":
                new_asig = (paciente, consulta, hora_str, new_value, fase)
            elif change_type == "consulta":
                new_asig = (paciente, new_value, hora_str, medico, fase)
            
            if new_asig:
                modified_solution_attempt = list(temp_solution) # Crear una nueva lista para el intento
                modified_solution_attempt[idx_to_change] = new_asig
                new_cost = self.calcular_coste(modified_solution_attempt)
                
                if new_cost < current_best_cost:
                    current_best_cost = new_cost
                    current_best_solution = modified_solution_attempt # Actualizar la mejor solución de la búsqueda local

        return current_best_solution

    def plot_convergence(self):
        if not self.total_costs:
            print("No hay datos para graficar convergencia.")
            return

        plt.figure(figsize=(10, 6))
        plt.plot(self.total_costs, marker='o', linestyle='-')
        plt.xlabel('Iteración')
        plt.ylabel('Mejor Costo Encontrado')
        plt.title('Convergencia del Algoritmo ACO')
        plt.grid(True)
        
        plot_dir = "/app/plots"
        os.makedirs(plot_dir, exist_ok=True)
        
        try:
            plt.savefig(os.path.join(plot_dir, "convergencia_aco.png"))
            print(f"Gráfico guardado en {os.path.join(plot_dir, 'convergencia_aco.png')}")
        except Exception as e:
            print(f"Error guardando gráfico: {e}")
        plt.close()

    def get_execution_time(self):
        return self.execution_time