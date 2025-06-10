import random
from typing import List, Dict, Tuple, Set, TYPE_CHECKING
from collections import defaultdict
import datetime

if TYPE_CHECKING:
    from Standard.Graph import Graph

class Ant:
    def __init__(self, graph: "Graph", paciente_to_estudio_info: Dict[str, Dict],
                 pacientes: List[str], duracion_consultas: int,
                 num_dias_planificacion: int,
                 alpha: float = 1.0, beta: float = 1.0,
                 max_fases_por_dia_paciente: int = 2):
        self.graph = graph
        self.alpha = alpha
        self.beta = beta
        self.visited: List[Tuple] = [] # Tuple: (pac, cons, day, hora_str, personal, fase)
        
        self.paciente_to_estudio_info = paciente_to_estudio_info
        
        self.pacientes = pacientes 
        # Progreso: {paciente: {fase: (dia, hora_str)}}
        self.pacientes_progreso = defaultdict(lambda: defaultdict(tuple))
        # Contador de fases por paciente por día: {paciente: {dia: numero_fases}}
        self.paciente_dia_fase_contador = defaultdict(lambda: defaultdict(int))

        self.duracion_consultas = duracion_consultas
        self.num_dias_planificacion = num_dias_planificacion
        self.current_node: Tuple = None
        self.total_cost: float = 0.0
        self.valid_solution = False
        self.max_fases_por_dia_paciente = max_fases_por_dia_paciente

    def choose_next_node(self) -> Tuple:
        """ Elige el siguiente nodo basado en la heurística y las feromonas."""
        if self.current_node is None:
            valid_initial_nodes = [
                node for node in self.graph.nodes
                if node[0] in self.paciente_to_estudio_info and \
                   self.paciente_to_estudio_info[node[0]]["orden_fases"].get(node[5]) == 1
            ]
            return random.choice(valid_initial_nodes) if valid_initial_nodes else None
        else:
            candidates = self.graph.edges.get(self.current_node, [])

            filtered_candidates = []
            for node_candidate in candidates:
                paciente_candidato = node_candidate[0]
                dia_candidato = node_candidate[2]
                fase_candidata = node_candidate[5]

                if paciente_candidato not in self.paciente_to_estudio_info:
                    continue

                info_estudio_candidato = self.paciente_to_estudio_info[paciente_candidato]

                if len(self.pacientes_progreso.get(paciente_candidato, {})) >= len(info_estudio_candidato["orden_fases"]):
                    continue # Paciente ya completó todas sus fases

                if fase_candidata in self.pacientes_progreso.get(paciente_candidato, {}):
                    continue # Fase ya programada para este paciente

                # Maximo N fases por paciente por día
                if self.paciente_dia_fase_contador[paciente_candidato][dia_candidato] >= self.max_fases_por_dia_paciente:
                    continue 
                
                filtered_candidates.append(node_candidate)

            if not filtered_candidates:
                return None

            candidate_list = []
            probabilities = []
            total_prob_weight = 0.0

            for node_cand in filtered_candidates:
                heuristic = self.calcular_heuristica(node_cand)
                pheromone = self.graph.get_pheromone(self.current_node, node_cand)
                candidate_weight = (pheromone ** self.alpha) * (heuristic ** self.beta)

                candidate_list.append(node_cand)
                probabilities.append(candidate_weight)
                total_prob_weight += candidate_weight

            normalized_probabilities = [p / total_prob_weight for p in probabilities]
            return random.choices(candidate_list, weights=normalized_probabilities, k=1)[0]


    def calcular_heuristica(self, node_to_evaluate: Tuple) -> float:
        """
        Calcula la heurística para un nodo dado, considerando restricciones de tiempo y recursos.
        Nodo: (paciente, consulta, dia_idx, hora_str, personal_instancia, fase_nombre)
        """
        pac_eval, con_eval, day_eval, hora_eval_str, personal_instancia_eval, fase_eval = node_to_evaluate

        score = 10.0

        if pac_eval not in self.paciente_to_estudio_info:
             return 0.001 
        
        # Máximo N fases por paciente por día
        if self.paciente_dia_fase_contador[pac_eval][day_eval] >= self.max_fases_por_dia_paciente:
            return 0.0001 # Heurística muy baja

        try:
            hora_parts_eval = hora_eval_str.split(':')
            node_eval_mins_of_day = int(hora_parts_eval[0]) * 60 + int(hora_parts_eval[1])
        except Exception:
            raise ValueError(f"Cadena de hora mal formada: {hora_eval_str}")
        if self.current_node:
            # curr_node: (pac, cons, day, hora_str, personal_instancia, fase)
            curr_pac, _, curr_day, curr_hora_str, _, curr_fase = self.current_node

            if pac_eval == curr_pac: # Mismo paciente
                try:
                    current_hora_parts = curr_hora_str.split(':')
                    current_node_mins_of_day = int(current_hora_parts[0]) * 60 + int(current_hora_parts[1])
                    current_node_end_mins_of_day = current_node_mins_of_day + self.duracion_consultas
                except ValueError: return 0.001

                if day_eval == curr_day:
                    if node_eval_mins_of_day < current_node_end_mins_of_day:
                         score -= 1000.0 # Fuerte penalización por solapamiento del mismo paciente en el mismo día
                    else:
                        tiempo_espera_mismo_paciente_dia = node_eval_mins_of_day - current_node_end_mins_of_day
                        bonus_menor_tiempo_espera = 100.0
                        if tiempo_espera_mismo_paciente_dia <= 120: # Hasta 2 horas
                            factor_prontitud = (120.0 - tiempo_espera_mismo_paciente_dia) / 120.0
                            score += factor_prontitud * bonus_menor_tiempo_espera
                elif day_eval < curr_day:
                    score -= 2000.0 # Penalización por ir hacia atrás en días para el mismo paciente

        node_eval_end_mins_of_day = node_eval_mins_of_day + self.duracion_consultas

        # Chequear conflictos de recursos (personal/consulta) con nodos ya visitados
        for v_node in self.visited:
            v_pac, v_con, v_day, v_hora_str, v_personal_instancia, v_fase = v_node

            if v_day == day_eval: # Conflicto de recurso solo si es en el mismo día
                try:
                    v_hora_parts = v_hora_str.split(':')
                    v_mins_of_day = int(v_hora_parts[0]) * 60 + int(v_hora_parts[1])
                    v_end_mins_of_day = v_mins_of_day + self.duracion_consultas
                except ValueError: continue

                # Comprobar superposición de tiempo
                time_overlap = (node_eval_mins_of_day < v_end_mins_of_day and
                                v_mins_of_day < node_eval_end_mins_of_day)

                if time_overlap:
                    if v_personal_instancia == personal_instancia_eval: # Misma instancia de personal
                        score -= 10000.0
                    if v_con == con_eval and v_pac != pac_eval: # Misma consulta
                        score -= 10000.0

        return max(0.001, score)


    def move(self, node: Tuple):
        """ Mueve la hormiga al siguiente nodo, actualizando su estado y progreso."""
        self.current_node = node
        self.visited.append(node)
        # Nodo: (paciente, consulta, dia_idx, hora_str, personal_instancia, fase_nombre)
        paciente, _, dia_idx, hora_str, _, fase = node
        self.pacientes_progreso[paciente][fase] = (dia_idx, hora_str)
        self.paciente_dia_fase_contador[paciente][dia_idx] += 1
        
        num_total_fases_programadas = sum(len(fases_dict) for fases_dict in self.pacientes_progreso.values())
        
        num_total_fases_esperadas = 0
        for p_id in self.pacientes: 
            if p_id in self.paciente_to_estudio_info:
                 num_total_fases_esperadas += len(self.paciente_to_estudio_info[p_id]["orden_fases"])

        if num_total_fases_programadas == num_total_fases_esperadas and num_total_fases_esperadas > 0 :
            self.valid_solution = True
        else:
            self.valid_solution = False