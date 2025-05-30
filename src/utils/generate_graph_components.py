from typing import List, Tuple, Dict, Any
from collections import defaultdict
import datetime

def construir_mapeo_paciente_info(tipos_estudio_data: List[Dict]) -> Dict:
    """
    Crea un mapeo de cada paciente a la información relevante de su estudio,
    incluyendo el orden de sus fases y la fase máxima.
    """
    paciente_a_estudio_info = {}
    for estudio in tipos_estudio_data:
        nombre_estudio = estudio["nombre_estudio"]
        orden_fases_estudio = estudio["orden_fases"]
        max_orden_estudio = 0
        if orden_fases_estudio: # Asegurarse de que orden_fases_estudio no esté vacío
            max_orden_estudio = max(orden_fases_estudio.values())

        for paciente in estudio["pacientes"]:
            paciente_a_estudio_info[paciente] = {
                "orden_fases": orden_fases_estudio,
                "max_orden": max_orden_estudio,
                "nombre_estudio": nombre_estudio
            }
    return paciente_a_estudio_info

def generar_nodos(config_data: Dict[str, Any], 
                  horas_disponibles: List[str]
                  ) -> List[Tuple]:
    """
    Genera nodos posibles del grafo. Optimizado para solo considerar
    fases relevantes y horas de inicio viables para completar el estudio.
    
    Cada nodo representa una posible asignación de:
    (paciente, consulta, hora, médico, fase)
    """
    nodos = []
    consultas = config_data["consultas"]
    medicos = config_data["medicos"]
    # intervalo_minutos = config_data["intervalo_consultas_minutos"] # No se usa directamente aquí, pero sí para la lógica conceptual

    map_hora_to_idx = {hora_str: idx for idx, hora_str in enumerate(horas_disponibles)}
    num_total_slots_disponibles = len(horas_disponibles)

    for estudio_config_info in config_data["tipos_estudio"]:
        pacientes_del_estudio = estudio_config_info["pacientes"]
        fases_del_estudio_nombres = estudio_config_info["fases"] 
        orden_fases_estudio = estudio_config_info["orden_fases"] 
        
        if not orden_fases_estudio: 
            continue
            
        num_fases_para_este_estudio = len(orden_fases_estudio)
        if num_fases_para_este_estudio == 0:
            continue
        
        for p in pacientes_del_estudio:
            for f_nombre in fases_del_estudio_nombres: # Iterar sobre todas las fases definidas para el estudio
                # Verificar si esta fase tiene un orden definido
                orden_actual_fase = orden_fases_estudio.get(f_nombre)
                if orden_actual_fase is None: # Si una fase listada no tiene orden, se ignora para la generación de nodos
                    raise ValueError(f"Fase '{f_nombre}' del estudio '{estudio_config_info['nombre_estudio']}' no tiene orden definido.")

                es_primera_fase_del_paciente = (orden_actual_fase == 1)

                for c in consultas:
                    for h_idx, h_str in enumerate(horas_disponibles):
                        if es_primera_fase_del_paciente:
                            slots_restantes_desde_h = num_total_slots_disponibles - h_idx
                            if slots_restantes_desde_h < num_fases_para_este_estudio:
                                # Si no hay suficientes slots restantes para completar el estudio, se omite esta hora
                                break
                        
                        for m in medicos:
                            nodos.append((p, c, h_str, m, f_nombre))

    print(f"Generated {len(nodos)} nodes (optimized with initial viability check).")
    return nodos

def generar_aristas(nodos: List[Tuple], 
                    paciente_info: Dict[str, Dict[str, Any]], 
                    duracion_consulta_minutos: int, 
                    horas_disponibles_str_list: List[str] 
                   ) -> Dict[Tuple, List[Tuple]]:
    """
    Genera las aristas del grafo aplicando restricciones de secuenciación.
    Utiliza paciente_info para obtener el orden de fases específico de cada paciente.
    Prohíbe conectar fases del mismo paciente en la misma hora o solapadas.
    """
    aristas = defaultdict(list)
    num_nodos = len(nodos)
    if num_nodos == 0:
        print("No hay nodos para generar aristas.")
        return aristas
        
    print(f"Generating aristas for {num_nodos} nodes...")

    horas_en_minutos_cache = {}
    for h_str in horas_disponibles_str_list: 
        try:
            dt_obj = datetime.datetime.strptime(h_str, "%H:%M")
            horas_en_minutos_cache[h_str] = dt_obj.hour * 60 + dt_obj.minute
        except ValueError:
            continue

    processed_nodes_count = 0 

    for i, nodo1 in enumerate(nodos):
        processed_nodes_count += 1
        # Imprimir progreso con menos frecuencia para no ralentizar demasiado
        if processed_nodes_count % (max(1, num_nodos // 10)) == 0 or processed_nodes_count == num_nodos : 
             print(f"  Aristas: Procesando nodo Origen {processed_nodes_count}/{num_nodos} ({(processed_nodes_count/num_nodos*100):.1f}%) - Aristas encontradas: {sum(len(v) for v in aristas.values())}")
        
        p1, c1, h1_str, m1, f1 = nodo1
        info_p1 = paciente_info.get(p1)
        if not info_p1: continue 

        h1_min = horas_en_minutos_cache.get(h1_str)
        if h1_min is None: continue 

        h1_fin_min = h1_min + duracion_consulta_minutos

        orden_fases_p1 = info_p1["orden_fases"]
        if not orden_fases_p1: continue # Si el paciente no tiene orden de fases definido
        
        max_orden_p1 = info_p1["max_orden"]
        orden_f1 = orden_fases_p1.get(f1)
        if orden_f1 is None: continue # Fase de nodo1 no tiene orden definido

        for nodo2 in nodos: 
            if nodo1 == nodo2:
                continue

            p2, c2, h2_str, m2, f2 = nodo2
            
            h2_min = horas_en_minutos_cache.get(h2_str)
            if h2_min is None: continue 

            # Restricción de recursos GENERAL para diferentes pacientes en la misma hora de inicio
            if h1_str == h2_str and p1 != p2:
                if m1 == m2 or c1 == c2:
                    continue
            
            info_p2 = paciente_info.get(p2)
            if not info_p2: continue

            orden_fases_p2 = info_p2["orden_fases"]
            if not orden_fases_p2: continue

            orden_f2 = orden_fases_p2.get(f2)
            if orden_f2 is None: continue # Fase de nodo2 no tiene orden definido

            # Caso 1: Mismo paciente (p1 == p2)
            if p1 == p2:
                # Condición 1: La fase f2 debe ser la siguiente a f1 en el orden del estudio
                es_siguiente_fase = (orden_f2 == orden_f1 + 1)
                
                if es_siguiente_fase:
                    # Condición 2: La hora de inicio de f2 (h2_min) debe ser >= que la hora de fin de f1 (h1_fin_min)
                    if h2_min >= h1_fin_min:
                        aristas[nodo1].append(nodo2)
            
            # Caso 2: Diferentes pacientes (p1 != p2)
            else:
                es_ultima_fase_p1 = (orden_f1 == max_orden_p1)
                es_primera_fase_p2 = (orden_f2 == 1)

                # La fase f2 debe ser la primera fase del paciente p2
                if es_ultima_fase_p1 and es_primera_fase_p2:
                    aristas[nodo1].append(nodo2)


    print(f"Generated {sum(len(v) for v in aristas.values())} aristas.")
    return aristas