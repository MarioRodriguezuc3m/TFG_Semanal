import random
from typing import List, Dict, Tuple, Set, TYPE_CHECKING
from collections import defaultdict
import datetime

if TYPE_CHECKING:
    from Standard.Graph import Graph

class Ant:
    def __init__(self, graph: "Graph", paciente_to_estudio_info: Dict[str, Dict], pacientes: List[str],duracion_consultas:int, alpha: float = 1.0, beta: float = 1.0):
        self.graph = graph
        self.alpha = alpha
        self.beta = beta
        self.visited: List[Tuple] = []
        
        # Info del estudio por paciente
        self.paciente_to_estudio_info = paciente_to_estudio_info
        
        self.pacientes = pacientes 
        self.pacientes_progreso = defaultdict(dict) # {paciente: {fase: hora}}
        self.duracion_consultas = duracion_consultas
        self.current_node: Tuple = None
        self.total_cost: float = 0.0
        self.valid_solution = False

    def choose_next_node(self) -> Tuple:
        if self.current_node is None:
            # Elegir nodos iniciales válidos (primera fase del estudio)
            valid_initial_nodes = [
                node for node in self.graph.nodes
                if node[0] in self.paciente_to_estudio_info and \
                   self.paciente_to_estudio_info[node[0]]["orden_fases"].get(node[4]) == 1
            ]
            return random.choice(valid_initial_nodes) if valid_initial_nodes else None
        else:
            candidates = self.graph.edges.get(self.current_node, [])
            
            # Filtrar candidatos válidos
            filtered_candidates = []
            for node in candidates:
                paciente_candidato = node[0]
                fase_candidata = node[4]

                if paciente_candidato not in self.paciente_to_estudio_info:
                    continue 

                info_estudio_candidato = self.paciente_to_estudio_info[paciente_candidato]
                
                # Evitar pacientes que ya completaron todas las fases
                if len(self.pacientes_progreso[paciente_candidato]) >= len(info_estudio_candidato["orden_fases"]):
                    continue
                
                # Evitar programar la misma fase dos veces
                if fase_candidata in self.pacientes_progreso[paciente_candidato]:
                    continue
                
                filtered_candidates.append(node)

            if not filtered_candidates:
                return None

            candidate_list = []
            probabilities = []
            total_prob_weight = 0.0

            for node in filtered_candidates:
                heuristic = self.calcular_heuristica(node)
                pheromone = self.graph.get_pheromone(self.current_node, node)
                candidate_weight = (pheromone ** self.alpha) * (heuristic ** self.beta)
                
                candidate_list.append(node)
                probabilities.append(candidate_weight)
                total_prob_weight += candidate_weight

            # Normalizar y elegir
            normalized_probabilities = [p / total_prob_weight for p in probabilities]
            return random.choices(candidate_list, weights=normalized_probabilities, k=1)[0]


    def calcular_heuristica(self, node_to_evaluate: Tuple) -> float:
        paciente_eval, consulta_eval, hora_str_eval, medico_eval, fase_eval = node_to_evaluate
        
        score = 10.0 # Base score
        
        if paciente_eval not in self.paciente_to_estudio_info:
             return 0.1 
        
        hora_parts_eval = hora_str_eval.split(':')
        node_eval_mins = int(hora_parts_eval[0]) * 60 + int(hora_parts_eval[1])
        
        # Verificar si el paciente del proximo nodo es el mismo que el del actual
        if self.current_node:
            curr_paciente, _, curr_hora_str, _, curr_fase = self.current_node
            
            if paciente_eval == curr_paciente: # Si es el mismo paciente
                current_hora_parts = curr_hora_str.split(':')
                current_node_mins = int(current_hora_parts[0]) * 60 + int(current_hora_parts[1])
                current_node_end_mins = current_node_mins + self.duracion_consultas

                # Penalización si el nodo a evaluar empieza ANTES
                if node_eval_mins < current_node_end_mins:
                     score -= 100.0 # Fuerte penalización por solapamiento del mismo paciente.
                else:
                    # Si el nodo a evaluar empieza DESPUÉS O AL MISMO TIEMPO que termina el actual.
                    tiempo_espera_mismo_paciente = node_eval_mins - current_node_end_mins
                    bonus_menor_tiempo_espera = 100.0 # Ajustable
                    
                    # Bonus por empezar la siguiente consulta lo antes posible: de 0 a 120 minutos de espera.
                    if tiempo_espera_mismo_paciente <= 120: # Hasta 2 horas de espera
                        # Factor de prontitud: 1.0 para espera 0, 0.0 para espera 120
                        factor_prontitud = (120.0 - tiempo_espera_mismo_paciente) / 120.0
                        score += factor_prontitud * bonus_menor_tiempo_espera
        
        node_eval_end_mins = node_eval_mins + self.duracion_consultas
        
        medico_count_conflict = 0
        consulta_count_conflict = 0
        
        # Chequear conflictos con nodos ya visitados
        for v_node in self.visited:
            v_paciente, v_consulta, v_hora_str, v_medico, v_fase = v_node
            
            v_hora_parts = v_hora_str.split(':')
            v_mins = int(v_hora_parts[0]) * 60 + int(v_hora_parts[1])
            v_end_mins = v_mins + self.duracion_consultas
            
            # Comprobar superposición de tiempo entre el nodo a evaluar y un nodo visitado
            if node_eval_mins < v_end_mins and v_mins < node_eval_end_mins: # Hay solapamiento temporal
                if v_medico == medico_eval:
                    score -= 10000.0 
                    medico_count_conflict +=1
                if v_consulta == consulta_eval:
                    score -= 10000.0 
                    consulta_count_conflict +=1
        
        # Bonus si no hay conflictos
        if medico_count_conflict == 0: score += 3.0
        if consulta_count_conflict == 0: score += 3.0
        
        return max(0.001, score) # Evitar heurística cero o negativa


    def move(self, node: Tuple):
        self.current_node = node
        self.visited.append(node)
        paciente, _, hora, _ , fase = node
        self.pacientes_progreso[paciente][fase] = hora 
        
        # Verificar si la solución está completa
        num_total_fases_programadas = sum(len(fases) for fases in self.pacientes_progreso.values())
        
        num_total_fases_esperadas = 0
        for p_id in self.pacientes: 
            if p_id in self.paciente_to_estudio_info:
                 num_total_fases_esperadas += len(self.paciente_to_estudio_info[p_id]["orden_fases"])

        if num_total_fases_programadas == num_total_fases_esperadas and num_total_fases_esperadas > 0 :
            # Solución estructuralmente completa (se han realizado todas las asignaciones requeridas).
            self.valid_solution = True
        else:
            self.valid_solution = False


    def _fases_en_orden_correcto(self, paciente: str, fases_paciente_progreso: Dict) -> bool:
        """
        Verifica si las fases están completas y en orden correcto
        """
        if paciente not in self.paciente_to_estudio_info:
            return False 
        
        info_estudio = self.paciente_to_estudio_info[paciente]
        orden_fases_definicion = info_estudio["orden_fases"]
        
        # Verificar que todas las fases estén programadas
        if len(fases_paciente_progreso) != len(orden_fases_definicion):
            return False

        # Verificar orden correcto
        fases_programadas_con_orden = []
        for fase_nombre, hora_asignada in fases_paciente_progreso.items():
            if fase_nombre not in orden_fases_definicion:
                return False 
            orden_definido = orden_fases_definicion[fase_nombre]
            fases_programadas_con_orden.append((orden_definido, hora_asignada, fase_nombre)) 
        
        # Ordenar por el orden definido
        fases_programadas_con_orden.sort(key=lambda x: x[0])
        
        # Verificar secuencia (1, 2, 3, ...)
        for i, (orden, _, _) in enumerate(fases_programadas_con_orden):
            if orden != i + 1:
                return False 
        
        return True