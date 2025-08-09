from MinMax.MinMaxAco import MinMaxACO
from MinMax.MinMaxGraph import MinMaxGraph 
from utils.generate_graph_components import generar_nodos, generar_aristas, construir_mapeo_paciente_info
from utils.plot_gantt_solution import plot_gantt_chart
import random
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, time # time es necesario para datetime.strptime(...).time()
from typing import List

def get_configuration(config_path='/app/src/MinMax/config.json'):
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
            expected_keys = ["tipos_estudio", "consultas", "hora_inicio", "hora_fin",
                             "intervalo_consultas_minutos", "num_dias_planificacion",
                             "roles", "personal", "cargos"]
            if not all(key in config for key in expected_keys):
                print(f"Error: Faltan claves en la configuración. Esperadas: {', '.join(expected_keys)}.")
                return None

            # Validar tipo de intervalo_consultas_minutos
            if not isinstance(config["intervalo_consultas_minutos"], int) or config["intervalo_consultas_minutos"] <= 0:
                print("Error: 'intervalo_consultas_minutos' debe ser un entero positivo."); return None
            if not isinstance(config["num_dias_planificacion"], int) or config["num_dias_planificacion"] <= 0:
                print("Error: 'num_dias_planificacion' debe ser un entero positivo."); return None
            try:
                datetime.strptime(config["hora_inicio"], "%H:%M")
                datetime.strptime(config["hora_fin"], "%H:%M")
            except ValueError:
                print("Error: 'hora_inicio' o 'hora_fin' tienen formato incorrecto. Usar HH:MM."); return None

            for estudio in config["tipos_estudio"]:
                if not all(k in estudio for k in ["nombre_estudio", "pacientes", "fases", "orden_fases"]):
                    print(f"Error en estudio {estudio.get('nombre_estudio', 'N/A')}. Faltan claves."); return None
            
            # Validaciones de roles, personal, cargos
            if not isinstance(config.get("roles"), list) or not all(isinstance(r, str) for r in config["roles"]):
                print("Error: 'roles' debe ser una lista de strings."); return None
            if not isinstance(config.get("personal"), dict):
                print("Error: 'personal' debe ser un diccionario."); return None
            for rol, cantidad in config["personal"].items():
                if rol not in config["roles"]:
                    print(f"Error: Rol '{rol}' en 'personal' no definido en 'roles'."); return None
                if not isinstance(cantidad, int) or cantidad <= 0:
                    print(f"Error: Cantidad para rol '{rol}' debe ser entero positivo."); return None
            if not isinstance(config.get("cargos"), dict):
                print("Error: 'cargos' debe ser un diccionario."); return None
            
            all_defined_phases_in_studies = set()
            for estudio_cfg in config["tipos_estudio"]:
                all_defined_phases_in_studies.update(estudio_cfg["fases"])

            for rol, fases_asignadas in config["cargos"].items():
                if rol not in config["roles"]:
                    print(f"Error: Rol '{rol}' en 'cargos' no definido en 'roles'."); return None
                if not isinstance(fases_asignadas, list) or not all(isinstance(f, str) for f in fases_asignadas):
                    print(f"Error: Fases para rol '{rol}' deben ser lista de strings."); return None
            
            phases_covered_by_roles = set()
            for rol in config["cargos"]:
                phases_covered_by_roles.update(config["cargos"][rol])
            
            for phase_study in all_defined_phases_in_studies:
                if phase_study not in phases_covered_by_roles:
                    print(f"Error crítico: Fase '{phase_study}' no cubierta por ningún rol en 'cargos'.")
                    return None
            return config
    except Exception as e:
        print(f"Error inesperado al cargar configuración: {e}")
        return None

def get_aco_params(params_path='aco_params.json'):
    """
    Carga los parámetros del algoritmo ACO desde un archivo JSON y verifica que las claves sean correctas.
    """
    expected_keys = {"n_ants", "iterations", "alpha", "beta", "rho", "Q","pheromone_max", "pheromone_min"}
    try:
        with open(params_path, 'r') as file:
            params = json.load(file)
        # Se verifican las claves
        params_keys = set(params.keys())
        if params_keys != expected_keys:
            raise Exception(f"Advertencia: Las claves del archivo de parámetros no son correctas.\n"
                  f"Esperadas: {sorted(expected_keys)}\n"
                  f"Encontradas: {sorted(params_keys)}\n")
        return params
    except Exception as e:
        raise Exception(f"Error cargando parámetros de ACO: {e}")

def generar_horas_disponibles(hora_inicio_str: str, hora_fin_str: str, intervalo_minutos: int) -> List[str]:
    """Genera una lista de strings de tiempo ("HH:MM") para un día tipo."""
    horas = []
    try:
        start_time_obj = datetime.strptime(hora_inicio_str, "%H:%M").time()
        end_time_obj = datetime.strptime(hora_fin_str, "%H:%M").time()
    except ValueError:
        print("Error: Formato de hora_inicio o hora_fin inválido en generar_horas_disponibles. Use HH:MM.")
        return []

    if intervalo_minutos <= 0:
        print("Error: intervalo_consultas_minutos debe ser positivo en generar_horas_disponibles.")
        return []

    current_dt = datetime.combine(datetime.today(), start_time_obj)
    end_datetime_limit = datetime.combine(datetime.today(), end_time_obj)

    while current_dt < end_datetime_limit:
        horas.append(current_dt.strftime("%H:%M"))
        current_dt += timedelta(minutes=intervalo_minutos)
    return horas

if __name__ == "__main__":
    # Especificar la ruta al config.json de MinMax
    config_file_path = os.environ.get('ACO_CONFIG_PATH', 'src/MinMax/config.json')
    aco_params_path = os.environ.get('ACO_PARAMS_PATH', 'src/MinMax/params_config.json')
    plot_dir_path = os.environ.get('PLOT_DIR_PATH', 'plots/')
    gantt_filename = os.environ.get('GANTT_FILENAME', 'schedule_standard_MinMax.png')
    gantt_filepath = os.path.join(plot_dir_path, gantt_filename)
    config_data = get_configuration(config_file_path)
    aco_params = get_aco_params(aco_params_path)
    random.seed(777) # Para reproducibilidad de los resultados

    if config_data is None:
        print("No se pudo cargar la configuración para MinMax.")
        exit(1)

    # Definir nombre paciente 
    for i in range(len(config_data['tipos_estudio'])):
        estudio_config = config_data['tipos_estudio'][i]
        nombre_estudio = estudio_config.get("nombre_estudio", f"EstudioDesconocido_{i}")
        
        # Transformar nombres de pacientes
        if "pacientes" in estudio_config and isinstance(estudio_config["pacientes"], list):
            transformed_pacientes_list = []
            for p_generic in estudio_config["pacientes"]:
                transformed_name = f"{nombre_estudio}_{p_generic}"
                transformed_pacientes_list.append(transformed_name)
            
            config_data['tipos_estudio'][i]["pacientes"] = transformed_pacientes_list

    map_paciente_info = construir_mapeo_paciente_info(config_data['tipos_estudio'])
    num_dias_planificacion = config_data['num_dias_planificacion'] # Cargar desde el config
    max_fases_por_dia_paciente = config_data.get('max_fases_por_dia_paciente', 2)

    horas_disponibles_un_dia = generar_horas_disponibles(
        config_data['hora_inicio'],
        config_data['hora_fin'],
        config_data['intervalo_consultas_minutos']
    )

    if not horas_disponibles_un_dia:
        print("Error: No se pudieron generar las horas disponibles para un día.")
        exit(1)
    
    print(f"Horas disponibles generadas (por día tipo): {horas_disponibles_un_dia}")
    print(f"Número de días para planificación: {num_dias_planificacion}")

    # Generar instancias de personal
    lista_personal_instancias = []
    for rol, cantidad in config_data["personal"].items():
        for i in range(1, cantidad + 1):
            lista_personal_instancias.append(f"{rol}_{i}")
    print(f"Instancias de personal generadas: {lista_personal_instancias}")

    # Generar componentes del grafo
    nodos = generar_nodos(config_data, horas_disponibles_un_dia, num_dias_planificacion,lista_personal_instancias,max_fases_por_dia_paciente)
    if not nodos:
        print("Error generando nodos. Verifique la configuración y las funciones de generación.")
        exit(1)
        
    aristas = generar_aristas(nodos, map_paciente_info,
                        duracion_consulta_minutos=config_data['intervalo_consultas_minutos'],
                        horas_disponibles_str_list=horas_disponibles_un_dia)
    
    # Usar MinMaxGraph
    min_max_graph = MinMaxGraph(
        nodes=nodos,
        edges=aristas,
        pheromone_max=aco_params["pheromone_max"],  # Valor máximo de feromonas (tau_max)
        pheromone_min=aco_params["pheromone_min"],   # Valor mínimo de feromonas (tau_min)
    )
    
    # Configurar y ejecutar ACO
    aco_minmax = MinMaxACO(
        graph=min_max_graph,
        config_data=config_data,
        horas_disponibles=horas_disponibles_un_dia,
        num_dias_planificacion=num_dias_planificacion,
        lista_personal_instancias=lista_personal_instancias,
        n_ants=aco_params["n_ants"],
        iterations=aco_params["iterations"],
        alpha=aco_params["alpha"],
        beta=aco_params["beta"],
        rho=aco_params["rho"],
        Q=aco_params["Q"]
    )
    
    print("Ejecutando MinMaxACO...")
    best_solution, best_cost = aco_minmax.run()
    aco_minmax.plot_convergence(output_dir=plot_dir_path) # Llama al método de convergencia de MinMaxACO

    if best_solution:
        asignaciones_por_paciente = defaultdict(list)
        for asignacion_tuple in best_solution: # Agrupa asignaciones por paciente
            paciente = asignacion_tuple[0]
            asignaciones_por_paciente[paciente].append(asignacion_tuple)
        
        intervalo_global_min = config_data['intervalo_consultas_minutos']

        print("\n--- Mejor Solución Encontrada (MinMaxACO) ---")
        for paciente_id in sorted(asignaciones_por_paciente.keys()):
            asignaciones_paciente = asignaciones_por_paciente[paciente_id]
            print(f"Paciente: {paciente_id}")
            
            info_estudio_paciente = aco_minmax.paciente_to_estudio.get(paciente_id)
            if info_estudio_paciente:
                print(f"  Estudio: {info_estudio_paciente['nombre_estudio']}")
                
                # Ordena asignaciones por orden de fase, día y hora
                asignaciones_ordenadas = sorted(
                    asignaciones_paciente, 
                    key=lambda asign_tuple: (
                        info_estudio_paciente['orden_fases'].get(asign_tuple[5], float('inf')),
                        asign_tuple[2],
                        datetime.strptime(asign_tuple[3], "%H:%M").time()
                    )
                )
                
                for asign_tuple_ordenada in asignaciones_ordenadas:
                    _, consulta, dia_idx, hora_str, medico, fase = asign_tuple_ordenada
                    orden = info_estudio_paciente['orden_fases'].get(fase, "N/A")
                    duracion = intervalo_global_min 
                    print(f"  Día {dia_idx + 1}, Fase {orden}. {fase} - {hora_str} ({duracion}min) - Consulta: {consulta} - Médico: {medico}")
            else:
                # Si no se encuentra información del estudio para el paciente
                print(f"  Advertencia: Información de estudio no encontrada para el paciente {paciente_id} en aco_minmax.paciente_to_estudio.")
        
        print(f"\nCosto total de la mejor solución (MinMaxACO): {best_cost:.2f}")
        if aco_minmax.execution_time is not None:
            print(f"Tiempo de ejecución (MinMaxACO): {aco_minmax.execution_time:.2f}s")

        # Gráfico de Gantt combinado para todos los pacientes
        if plot_gantt_chart:
            print("\nGenerando gráfico de línea de tiempo combinado (MinMaxACO)...")
            try:
                fases_duration_para_plot = {}
                all_configured_phase_names = set()
                for estudio_cfg in config_data['tipos_estudio']:
                    all_configured_phase_names.update(estudio_cfg['fases'])
                for phase_name in all_configured_phase_names:
                    fases_duration_para_plot[phase_name] = intervalo_global_min
                
                plot_start_hour_config = datetime.strptime(config_data['hora_inicio'], "%H:%M").hour
                plot_end_hour_config = datetime.strptime(config_data['hora_fin'], "%H:%M").hour
                
                plot_gantt_chart(
                    best_solution=best_solution, 
                    fases_duration_map=fases_duration_para_plot,
                    map_paciente_info=map_paciente_info, 
                    output_filepath=gantt_filepath,
                    num_dias_planificacion=num_dias_planificacion,
                    configured_start_hour=plot_start_hour_config,
                    configured_end_hour=plot_end_hour_config 
                )
            except Exception as e:
                print(f"Error generando el gráfico de línea de tiempo combinado (MinMaxACO): {e}")
                import traceback
                traceback.print_exc()
    else:
        print("\nNo se encontró ninguna solución válida con MinMaxACO.")
        if aco_minmax.execution_time is not None:
            print(f"Tiempo de ejecución (MinMaxACO): {aco_minmax.execution_time:.2f}s")