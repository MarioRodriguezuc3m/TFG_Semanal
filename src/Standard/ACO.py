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
    def __init__(self, graph: Graph, config_data: Dict, horas_disponibles: List[str], # Horas para un día tipo
                 num_dias_planificacion: int,
                 lista_personal_instancias: List[str],
                 n_ants: int = 10, iterations: int = 100,
                 alpha: float = 1.0, beta: float = 3.0, rho: float = 0.1, Q: float = 1.0):
        self.graph = graph
        self.config_data = config_data
        
        self.tipos_estudio = config_data["tipos_estudio"]
        self.consultas = config_data["consultas"]
        self.horas_un_dia = horas_disponibles
        self.num_dias_planificacion = num_dias_planificacion
        self.duracion_consultas = config_data.get("intervalo_consultas_minutos")

        # Atributos relacionados con roles y personal
        self.roles_config = config_data["roles"]
        self.personal_cantidad_config = config_data["personal"]
        self.cargos_config = config_data["cargos"]
        self.lista_personal_instancias = lista_personal_instancias

        # Mapeo de fase a roles que pueden realizarla
        self.fase_a_roles_compatibles = defaultdict(list)
        for rol, fases_asignadas in self.cargos_config.items():
            for fase in fases_asignadas:
                self.fase_a_roles_compatibles[fase].append(rol)

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
        self.max_fases_por_dia_paciente = config_data.get("max_fases_por_dia_paciente", 2)

    def run(self):
        """" Ejecuta el algoritmo ACO para encontrar la mejor solución de planificación """
        start_time = time.time()
        
        for iteration in range(self.iterations):
            ants = [Ant(self.graph, self.paciente_to_estudio, self.pacientes, self.duracion_consultas,
                        self.num_dias_planificacion, self.alpha, self.beta, self.max_fases_por_dia_paciente) for _ in range(self.n_ants)]
            
            iteration_best_cost = float('inf')
            iteration_best_solution = None

            for ant_idx, ant in enumerate(ants):
                max_steps = sum(len(self.paciente_to_estudio[p]["fases"]) for p in self.pacientes) * 2
                steps = 0
                # Reiniciar estado interno de la hormiga
                ant.visited = []
                ant.pacientes_progreso.clear()
                ant.paciente_dia_fase_contador.clear()
                ant.current_node = None
                ant.valid_solution = False
                
                while steps < max_steps and not ant.valid_solution:
                    next_node = ant.choose_next_node()
                    if next_node is None:
                        break
                    ant.move(next_node)
                    steps += 1

                if ant.valid_solution:
                    cost = self.calcular_coste(ant.visited)
                    ant.total_cost = cost # Almacenar el coste total en la hormiga
                    
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
                if self.best_solution is not None:
                    # Solo la mejor hormiga de la iteración actualiza
                    temp_ant_for_pheromone = Ant(self.graph, self.paciente_to_estudio, self.pacientes, self.duracion_consultas,
                                                self.num_dias_planificacion, self.alpha, self.beta, self.max_fases_por_dia_paciente)
                    temp_ant_for_pheromone.visited = iteration_best_solution # Mejor de la iteración
                    temp_ant_for_pheromone.total_cost = iteration_best_cost
                    self.graph.update_pheromone([temp_ant_for_pheromone], self.rho, self.Q)

            else: # No se encontró solución válida en esta iteración por ninguna hormiga
                self.graph.update_pheromone([], self.rho, self.Q) # Solo evaporar feromonas

            if iteration % 10 == 0:
                print(f"Iteración {iteration}/{self.iterations} - Mejor Costo Global: {self.best_cost if self.best_cost != float('inf') else 'N/A'}")
            
            # Registrar coste para gráfico de convergencia
            current_iter_display_cost = self.best_cost if self.best_cost != float('inf') else (iteration_best_cost if iteration_best_cost != float('inf') else None)
            if current_iter_display_cost is not None:
                self.total_costs.append(current_iter_display_cost)
            elif self.total_costs: # si no hay coste en esta iteración, repetir el último mejor conocido
                self.total_costs.append(self.total_costs[-1])

        end_time = time.time()
        self.execution_time = end_time - start_time

        return self.best_solution, self.best_cost

    def calcular_coste(self, asignaciones: List[Tuple]) -> float:
        """" Calcula el coste total de una solución de asignaciones """
        # Asignacion: (paciente, consulta, dia_idx, hora_str, personal, fase_nombre)
        if not asignaciones:
            return float('inf')

        fases_activas_detalle = []
        tiempos_pacientes = defaultdict(list)
        hora_str_to_min_cache = {} 
        coste_total = 0.0
        max_min_per_day = 24 * 60

        fases_por_paciente_dia = defaultdict(lambda: defaultdict(int))

        # PASO 1: Validar cada asignación individual y pre-procesar
        for asignacion_idx, asignacion in enumerate(asignaciones):
            paciente, consulta, dia_idx, hora_str, personal_instancia, fase_nombre = asignacion
            estudio_info_paciente = self.paciente_to_estudio[paciente]

            # Validar que el personal asignado puede realizar la fase
            rol_asignado = personal_instancia.split('_')[0]
            if rol_asignado not in self.cargos_config or fase_nombre not in self.cargos_config[rol_asignado]:
                coste_total += 75000 # Penalización por personal incorrecto para la fase
                continue

            # Contar fases por paciente y día
            fases_por_paciente_dia[paciente][dia_idx] += 1

            # Convertir hora string a minutos (con cache para eficiencia)
            if hora_str not in hora_str_to_min_cache:
                try:
                    hora_obj = datetime.datetime.strptime(hora_str, "%H:%M").time()
                    inicio_min_dia = hora_obj.hour * 60 + hora_obj.minute
                    hora_str_to_min_cache[hora_str] = inicio_min_dia
                except ValueError:
                    coste_total += 60000 # Penalización por formato de hora inválido
                    continue
            else:
                inicio_min_dia = hora_str_to_min_cache[hora_str]

            fin_min_dia = inicio_min_dia + self.duracion_consultas
            inicio_min_abs = dia_idx * max_min_per_day + inicio_min_dia
            fin_min_abs = dia_idx * max_min_per_day + fin_min_dia
            
            orden_fase = estudio_info_paciente["orden_fases"].get(fase_nombre)
            if orden_fase is None:
                coste_total += 46000 # Penalización por orden no definido
                continue

            # Guardar detalles de la fase para análisis posteriores
            fases_activas_detalle.append({
                'paciente': paciente, 'consulta': consulta, 'personal': personal_instancia, 'fase': fase_nombre,
                'dia_idx': dia_idx, 'hora_str': hora_str,
                'inicio_min_dia': inicio_min_dia, 'fin_min_dia': fin_min_dia, # Minutos dentro del día
                'inicio_min_abs': inicio_min_abs, 'fin_min_abs': fin_min_abs, # Minutos absolutos en la planificación
                'orden': orden_fase, 'original_tuple': asignacion, 'idx_original': asignacion_idx
            })
            tiempos_pacientes[paciente].append((orden_fase, dia_idx, inicio_min_abs, fin_min_abs, fase_nombre, inicio_min_dia))

        # Si hay errores graves de validación, retornar sin más análisis
        if coste_total > 0:
            return coste_total

        # PASO 1.5: Penalizar violación de "max_fases_por_dia_paciente" fases por paciente por día
        for pac, dias_data in fases_por_paciente_dia.items():
            for dia, count in dias_data.items():
                if count > self.max_fases_por_dia_paciente:
                    coste_total += 30000 * (count - self.max_fases_por_dia_paciente) # Penalización fuerte

        # PASO 2: Detectar conflictos de recursos (médicos, consultas) usando algoritmo de barrido sobre tiempo absoluto
        eventos = []
        # Crear eventos de inicio y fin para cada fase
        for i, f_activa in enumerate(fases_activas_detalle):
            # Eventos usan tiempo absoluto para que el barrido funcione entre días
            eventos.append((f_activa['inicio_min_abs'], 'start', i, f_activa['personal'], f_activa['consulta']))
            eventos.append((f_activa['fin_min_abs'], 'end', i, f_activa['personal'], f_activa['consulta']))
        
        eventos.sort() # Ordenar por tiempo

        consultas_ocupadas = defaultdict(int) # Contador de fases activas por consulta
        personal_ocupado = defaultdict(int) # Contador de fases activas por personal
        for t_abs, tipo_evento, idx_fase, personal_evento, consulta_evento in eventos:
            if tipo_evento == 'start':
                if personal_ocupado[personal_evento] > 0: coste_total += 20000
                personal_ocupado[personal_evento] += 1 # Personal ocupado
                if consultas_ocupadas[consulta_evento] > 0: coste_total += 20000
                consultas_ocupadas[consulta_evento] += 1 # Consulta ocupada
            else:
                personal_ocupado[personal_evento] -= 1
                consultas_ocupadas[consulta_evento] -= 1

        # PASO 3: Verificar secuencia y tiempos por paciente
        coste_por_dia_vacio = 500 # Penalización por cada día vacío entre citas del mismo paciente

        for paciente, fases_programadas_paciente in tiempos_pacientes.items():
            estudio_info = self.paciente_to_estudio[paciente]
            fases_programadas_paciente.sort(key=lambda x: (x[0], x[1], x[2])) 

            # Verificar que están todas las fases del estudio
            num_fases_definidas = len(estudio_info["orden_fases"])
            if len(fases_programadas_paciente) != num_fases_definidas:
                coste_total += 15000 * abs(num_fases_definidas - len(fases_programadas_paciente))
            
            orden_esperado = 1
            fin_fase_anterior_abs_min = -1
            dia_fase_anterior = -1

            for orden_actual, dia_actual, inicio_actual_abs_min, fin_actual_abs_min, fase_nombre_actual, inicio_actual_min_dia in fases_programadas_paciente:
                # Verificar que las fases están en el orden correcto
                if orden_actual != orden_esperado:
                    coste_total += 100000 # Penalización por orden incorrecto
                
                if fin_fase_anterior_abs_min != -1:  # No es la primera fase del paciente
                    if inicio_actual_abs_min < fin_fase_anterior_abs_min:
                        # Las fases se solapan 
                        coste_total += 50000 * (fin_fase_anterior_abs_min - inicio_actual_abs_min)
                    else:
                        # Calcular tiempo de espera entre fases
                        tiempo_espera_abs = inicio_actual_abs_min - fin_fase_anterior_abs_min
                        
                        if dia_actual == dia_fase_anterior: # Ambas fases en el MISMO DÍA
                            # Aplicar penalizaciones de espera intra-día
                            if tiempo_espera_abs > 120:  # Más de 2 horas de espera en el mismo día
                                coste_total += (tiempo_espera_abs - 120) * 2  # Penalización creciente
                            elif tiempo_espera_abs > 30:  # Más de 15 minutos en el mismo día
                                 coste_total += tiempo_espera_abs * 0.5  # Penalización leve
                        
                        elif dia_actual > dia_fase_anterior: # Fases en días diferentes
                            dias_vacios = dia_actual - dia_fase_anterior - 1
                            if dias_vacios > 0: # Penalizar días vacíos entre fases
                                coste_total += dias_vacios * coste_por_dia_vacio
                            
                fin_fase_anterior_abs_min = fin_actual_abs_min
                dia_fase_anterior = dia_actual # Actualizar el día de la fase anterior
                orden_esperado += 1
        
        return coste_total if coste_total > 0 else 0.1  # Evitar coste cero
        
    def _identificar_asignaciones_conflictivas(self, solution: List[Tuple]) -> List[int]:
        """" Identifica los índices de asignaciones conflictivas en una solución """
        # Asignacion: (paciente, consulta, dia_idx, hora_str, personal_instancia, fase_nombre)
        conflictive_indices = set()
        if not solution or len(solution) < 2:
            return []

        hora_str_to_min_cache = {}
        duracion_consulta_min = self.duracion_consultas

        processed_assignments = []
        for i, asignacion in enumerate(solution):
            if len(asignacion) != 6: continue
            paciente, consulta, dia_idx, hora_str, personal_instancia, fase = asignacion

            if hora_str not in hora_str_to_min_cache:
                try:
                    hora_obj = datetime.datetime.strptime(hora_str, "%H:%M").time()
                    inicio_min_dia = hora_obj.hour * 60 + hora_obj.minute
                    hora_str_to_min_cache[hora_str] = inicio_min_dia
                except ValueError: continue
            else:
                inicio_min_dia = hora_str_to_min_cache[hora_str]

            fin_min_dia = inicio_min_dia + duracion_consulta_min
            processed_assignments.append({
                'idx': i, 'paciente': paciente, 'consulta': consulta, 'dia_idx': dia_idx,
                'personal': personal_instancia, 'fase': fase,
                'inicio_min_dia': inicio_min_dia, 'fin_min_dia': fin_min_dia,
                'original_tuple': asignacion
            })

        # Comprobar conflictos entre pares de asignaciones
        for i in range(len(processed_assignments)):
            asig1 = processed_assignments[i]
            for j in range(i + 1, len(processed_assignments)):
                asig2 = processed_assignments[j]

                # Conflicto solo si es en el mismo día
                if asig1['dia_idx'] == asig2['dia_idx']:
                    # Comprobar solapamiento temporal
                    overlap = (asig1['inicio_min_dia'] < asig2['fin_min_dia'] and
                               asig2['inicio_min_dia'] < asig1['fin_min_dia'])

                    if overlap:
                        # Conflicto de personal (diferentes pacientes, mismo personal, mismo día y hora)
                        if asig1['personal'] == asig2['personal'] :
                            conflictive_indices.add(asig1['idx']); conflictive_indices.add(asig2['idx'])
                        if asig1['consulta'] == asig2['consulta']:
                            conflictive_indices.add(asig1['idx']); conflictive_indices.add(asig2['idx'])
        return list(conflictive_indices)


    def local_search(self, solution: List[Tuple]) -> List[Tuple]:
        """" Realiza una búsqueda local para intentar mejorar la solución dada """
        # Asignacion: (paciente, consulta, dia_idx, hora_str, personal, fase_nombre)
        current_best_solution = list(solution) # Copia de la solución actual
        current_best_cost = self.calcular_coste(current_best_solution)

        if not current_best_solution or current_best_cost == 0.1: # Si la solución es vacía o ya es óptima
            return current_best_solution

        num_improvement_attempts = 15 # Limitar intentos

        for attempt in range(num_improvement_attempts):
            if not current_best_solution: break # Evitar error si la solución está vacía
            
            temp_solution = list(current_best_solution) # Copia temporal de la solución actual
            conflictive_indices = self._identificar_asignaciones_conflictivas(temp_solution)
            
            idx_to_change = -1
            if conflictive_indices and random.random() < 0.9: # 90% de probabilidad de elegir un conflicto
                idx_to_change = random.choice(conflictive_indices)
            else:
                if not temp_solution: continue # Evitar error si temp_solution está vacía
                idx_to_change = random.randrange(len(temp_solution))

            if idx_to_change == -1 or idx_to_change >= len(temp_solution):
                continue

            original_assignment = temp_solution[idx_to_change]
            paciente, consulta, dia_idx, hora_str, personal_actual_instancia, fase = original_assignment

            change_options = []
            # Cambiar hora
            available_new_horas = [h for h in self.horas_un_dia if h != hora_str]
            if available_new_horas:
                change_options.append(("hora", random.choice(available_new_horas)))
            
            # Cambiar personal_instancia
            roles_compatibles_con_fase = self.fase_a_roles_compatibles.get(fase, [])
            available_new_personal_instancias = []
            if roles_compatibles_con_fase:
                for p_inst in self.lista_personal_instancias:
                    p_rol = p_inst.split('_')[0]
                    if p_rol in roles_compatibles_con_fase and p_inst != personal_actual_instancia:
                        available_new_personal_instancias.append(p_inst)
            if available_new_personal_instancias:
                change_options.append(("personal", random.choice(available_new_personal_instancias)))

            # Cambiar consulta
            available_new_consultas = [c for c in self.consultas if c != consulta]
            if available_new_consultas:
                change_options.append(("consulta", random.choice(available_new_consultas)))
            
            # Cambiar día
            available_new_dias = [d_idx for d_idx in range(self.num_dias_planificacion) if d_idx != dia_idx]
            if available_new_dias:
                change_options.append(("dia", random.choice(available_new_dias)))

            if not change_options:
                continue # No hay opciones de cambio para esta asignación

            change_type, new_value = random.choice(change_options)
            
            new_asig = None
            if change_type == "hora": new_asig = (paciente, consulta, dia_idx, new_value, personal_actual_instancia, fase)
            elif change_type == "personal": new_asig = (paciente, consulta, dia_idx, hora_str, new_value, fase)
            elif change_type == "consulta": new_asig = (paciente, new_value, dia_idx, hora_str, personal_actual_instancia, fase)
            elif change_type == "dia": new_asig = (paciente, consulta, new_value, hora_str, personal_actual_instancia, fase)
            
            if new_asig:
                modified_solution_attempt = list(temp_solution)
                modified_solution_attempt[idx_to_change] = new_asig
                new_cost = self.calcular_coste(modified_solution_attempt)
                if new_cost < current_best_cost:
                    current_best_cost = new_cost
                    current_best_solution = modified_solution_attempt
        return current_best_solution

    def plot_convergence(self):
        if not self.total_costs: print("No hay datos para graficar convergencia."); return
        plt.figure(figsize=(10, 6))
        plt.plot(self.total_costs, marker='o', linestyle='-')
        plt.xlabel('Iteración'); plt.ylabel('Mejor Costo Encontrado'); plt.title('Convergencia del Algoritmo ACO'); plt.grid(True)
        plot_dir = "/app/plots"; os.makedirs(plot_dir, exist_ok=True)
        try: plt.savefig(os.path.join(plot_dir, "convergencia_aco.png")); print(f"Gráfico guardado en {os.path.join(plot_dir, 'convergencia_aco.png')}")
        except Exception as e: print(f"Error guardando gráfico: {e}")
        plt.close() # Cerrar la figura para liberar memoria
