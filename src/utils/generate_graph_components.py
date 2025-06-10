from typing import List, Tuple, Dict, Any
from collections import defaultdict
import datetime
import math

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
        if orden_fases_estudio: 
            max_orden_estudio = max(orden_fases_estudio.values())

        for paciente in estudio["pacientes"]:
            paciente_a_estudio_info[paciente] = {
                "orden_fases": orden_fases_estudio,
                "max_orden": max_orden_estudio,
                "nombre_estudio": nombre_estudio
            }
    return paciente_a_estudio_info

def generar_nodos(config_data: Dict[str, Any], 
                  horas_disponibles_un_dia: List[str],
                  num_dias_planificacion: int,
                  lista_personal_instancias: List[str],
                  max_fases_por_dia_paciente: int = 2
                  ) -> List[Tuple]:
    """
    Genera nodos posibles del grafo para múltiples días, considerando roles y personal.
    Nodo: (paciente, consulta, dia_idx, hora_str, personal_instancia, fase_nombre)
    """
    nodos = []
    consultas = config_data["consultas"]
    cargos_fases_config = config_data["cargos"]

    num_slots_por_dia = len(horas_disponibles_un_dia)

    for estudio_config_info in config_data["tipos_estudio"]:
        pacientes_del_estudio = estudio_config_info["pacientes"]
        fases_del_estudio_nombres = estudio_config_info["fases"] 
        orden_fases_estudio = estudio_config_info["orden_fases"] 
        
        if not orden_fases_estudio: 
            continue
        
        num_fases_para_este_estudio = len(orden_fases_estudio)
        if num_fases_para_este_estudio == 0:
            continue
            
        # Mínimo de días necesarios solo por la restricción de fases/día
        min_dias_necesarios_por_limite_fases = math.ceil(num_fases_para_este_estudio / max_fases_por_dia_paciente)

        for p in pacientes_del_estudio:
            for f_nombre in fases_del_estudio_nombres: 
                orden_actual_fase = orden_fases_estudio.get(f_nombre)
                if orden_actual_fase is None: 
                    print(f"Advertencia: Fase '{f_nombre}' del estudio '{estudio_config_info['nombre_estudio']}' para paciente '{p}' no tiene orden definido. Se omite.")
                    continue

                es_primera_fase_del_paciente = (orden_actual_fase == 1)

                for c in consultas:
                    for dia_idx in range(num_dias_planificacion):
                        # Optimización de viabilidad para la PRIMERA fase del estudio
                        if es_primera_fase_del_paciente:
                            dias_restantes_reales = num_dias_planificacion - dia_idx
                            if dias_restantes_reales < min_dias_necesarios_por_limite_fases:
                                break # No hay suficientes días para completar el estudio

                        for h_idx, h_str in enumerate(horas_disponibles_un_dia):
                            if es_primera_fase_del_paciente:
                                # Optimización de viabilidad para la PRIMERA fase del paciente, verificando si hay suficientes horas disponibles
                                fases_posibles_en_slots_dia_actual = min(max_fases_por_dia_paciente, num_slots_por_dia - h_idx)
                                dias_completos_futuros = num_dias_planificacion - 1 - dia_idx
                                fases_posibles_en_slots_dias_futuros = dias_completos_futuros * max_fases_por_dia_paciente
                                
                                total_fases_alojables_globalmente = fases_posibles_en_slots_dia_actual + fases_posibles_en_slots_dias_futuros
                                
                                if total_fases_alojables_globalmente < num_fases_para_este_estudio:
                                    break # No hay suficientes slots/días restantes para el estudio desde esta hora

                            for personal_instancia in lista_personal_instancias:
                                rol_actual = personal_instancia.split('_')[0]

                                # Verificar si el rol actual puede realizar la fase actual
                                if rol_actual not in cargos_fases_config or \
                                   f_nombre not in cargos_fases_config[rol_actual]:
                                    continue # No puede hacer esta fase

                                # Si el personal puede realizar la fase, se crea el nodo
                                nodos.append((p, c, dia_idx, h_str, personal_instancia, f_nombre))

    print(f"Generados {len(nodos)} nodos a lo largo de {num_dias_planificacion} días con roles.")
    return nodos

def generar_aristas(nodos: List[Tuple],
                    paciente_info: Dict[str, Dict[str, Any]],
                    duracion_consulta_minutos: int,
                    horas_disponibles_str_list: List[str]
                   ) -> Dict[Tuple, List[Tuple]]:
    """
    Genera las aristas del grafo considerando días, horas y roles de personal.
    Nodo: (paciente, consulta, dia_idx, hora_str, personal_instancia, fase_nombre)
    """
    aristas = defaultdict(list)
    num_nodos = len(nodos)
    if num_nodos == 0:
        print("No hay nodos para generar aristas.")
        return aristas
        
    print(f"Generando aristas para {num_nodos} nodos...")

    # Caché para convertir "HH:MM" a minutos del día
    horas_min_del_dia_cache = {}
    for h_str in horas_disponibles_str_list: 
        try:
            dt_obj = datetime.datetime.strptime(h_str, "%H:%M")
            horas_min_del_dia_cache[h_str] = dt_obj.hour * 60 + dt_obj.minute
        except ValueError:
            raise ValueError(f"Formato de hora inválido: '{h_str}'. Debe ser 'HH:MM'.")

    processed_nodes_count = 0 

    for i, nodo1 in enumerate(nodos):
        processed_nodes_count += 1
        if processed_nodes_count % (max(1, num_nodos // 20)) == 0 or processed_nodes_count == num_nodos : 
             print(f"  Aristas: Procesando nodo Origen {processed_nodes_count}/{num_nodos} ({(processed_nodes_count/num_nodos*100):.1f}%) - Aristas encontradas: {sum(len(v) for v in aristas.values())}")

        # p1, c1, day1, h1_str, personal1, f1
        p1, c1, day1, h1_str, personal1, f1 = nodo1
        info_p1 = paciente_info.get(p1)
        if not info_p1: continue 

        h1_min_del_dia = horas_min_del_dia_cache.get(h1_str)
        if h1_min_del_dia is None: continue 
        h1_fin_min_del_dia = h1_min_del_dia + duracion_consulta_minutos

        orden_fases_p1 = info_p1["orden_fases"]
        if not orden_fases_p1: continue
        
        max_orden_p1 = info_p1["max_orden"]
        orden_f1 = orden_fases_p1.get(f1)
        if orden_f1 is None: continue

        for nodo2 in nodos: 
            if nodo1 == nodo2:
                continue

            p2, c2, day2, h2_str, personal2, f2 = nodo2

            h2_min_del_dia = horas_min_del_dia_cache.get(h2_str)
            if h2_min_del_dia is None: continue

            # Restricción de recursos GENERAL para diferentes pacientes en la misma hora de inicio
            if p1 != p2 and day1 == day2 and h1_str == h2_str: # Mismo día y hora
                if personal1 == personal2 or c1 == c2: # Misma instancia de personal o misma consulta
                    continue

            info_p2 = paciente_info.get(p2)
            if not info_p2: continue

            orden_fases_p2 = info_p2["orden_fases"]
            if not orden_fases_p2: continue

            orden_f2 = orden_fases_p2.get(f2)
            if orden_f2 is None: continue

            # Caso 1: Mismo paciente (p1 == p2)
            if p1 == p2:
                es_siguiente_fase = (orden_f2 == orden_f1 + 1)
                if es_siguiente_fase:
                    # Transiciones válidas:
                    # 1. Mismo día, f2 empieza después de que termine f1
                    # 2. f2 es un día posterior a f1
                    if day2 == day1:
                        if h2_min_del_dia >= h1_fin_min_del_dia:
                            aristas[nodo1].append(nodo2)
                    elif day2 > day1: # Fase 2 en día posterior
                        aristas[nodo1].append(nodo2)

            # Caso 2: Diferentes pacientes (p1 != p2)
            else: # p1 != p2
                es_ultima_fase_p1 = (orden_f1 == max_orden_p1)
                es_primera_fase_p2 = (orden_f2 == 1)

                if es_ultima_fase_p1 and es_primera_fase_p2:
                    aristas[nodo1].append(nodo2)

    print(f"Generadas {sum(len(v) for v in aristas.values())} aristas.")
    return aristas