from MinMax.MinMaxAco import MinMaxACO
from MinMax.MinMaxGraph import MinMaxGraph 
from utils.generate_graph_components import generar_nodos, generar_aristas, construir_mapeo_paciente_info
from utils.plot_gantt_solution import plot_gantt_chart

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, time
from typing import List

def get_configuration(config_path='/app/src/MinMax/config.json'):
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
            # Verificar claves principales
            expected_keys = ["tipos_estudio", "consultas", "hora_inicio", "hora_fin", "intervalo_consultas_minutos", "medicos"]
            if not all(key in config for key in expected_keys):
                print(f"Error: Faltan claves en la configuración. Esperadas: {', '.join(expected_keys)}.")
                return None

            # Validar tipo de intervalo_consultas_minutos
            if not isinstance(config["intervalo_consultas_minutos"], int) or config["intervalo_consultas_minutos"] <= 0:
                print("Error: 'intervalo_consultas_minutos' debe ser un entero positivo.")
                return None

            # Validar formato de horas
            try:
                datetime.strptime(config["hora_inicio"], "%H:%M")
                datetime.strptime(config["hora_fin"], "%H:%M")
            except ValueError:
                print("Error: 'hora_inicio' o 'hora_fin' tienen formato incorrecto. Usar HH:MM.")
                return None

            # Verificar estructura de estudios
            for estudio in config["tipos_estudio"]:
                if not all(k in estudio for k in ["nombre_estudio", "pacientes", "fases", "orden_fases"]):
                    print(f"Error: Estructura incorrecta en estudio {estudio.get('nombre_estudio', 'DESCONOCIDO')}. Se esperan: nombre_estudio, pacientes, fases, orden_fases.")
                    return None
                if "fases_duration" in estudio:
                    print(f"Advertencia: 'fases_duration' en estudio {estudio.get('nombre_estudio', 'DESCONOCIDO')} ya no se utiliza. Se usará el 'intervalo_consultas_minutos' global.")
            return config
    except Exception as e:
        print(f"Error inesperado al cargar configuración: {e}")
        return None

def generar_horas_disponibles(hora_inicio_str: str, hora_fin_str: str, intervalo_minutos: int) -> List[str]:
    """Genera una lista de strings de tiempo ("HH:MM") entre hora_inicio y hora_fin con el intervalo dado."""
    horas = []
    try:
        start_time_obj = datetime.strptime(hora_inicio_str, "%H:%M").time()
        end_time_obj = datetime.strptime(hora_fin_str, "%H:%M").time() # Hora límite para el inicio de un nuevo slot
    except ValueError:
        print("Error: Formato de hora_inicio o hora_fin inválido en generar_horas_disponibles. Use HH:MM.")
        return []

    if intervalo_minutos <= 0:
        print("Error: intervalo_consultas_minutos debe ser positivo en generar_horas_disponibles.")
        return []

    current_dt = datetime.combine(datetime.today(), start_time_obj)
    # El último slot debe empezar estrictamente antes de end_time_obj
    end_datetime_limit = datetime.combine(datetime.today(), end_time_obj)

    while current_dt < end_datetime_limit:
        horas.append(current_dt.strftime("%H:%M"))
        current_dt += timedelta(minutes=intervalo_minutos)

    return horas

if __name__ == "__main__":
    config_file_path = '/app/src/MinMax/config.json'
    config_data = get_configuration(config_file_path)

    if config_data is None:
        print("No se pudo cargar la configuración.")
        exit(1)

    map_paciente_info = construir_mapeo_paciente_info(config_data['tipos_estudio'])

    # Generar horas disponibles
    horas_disponibles = generar_horas_disponibles(
        config_data['hora_inicio'],
        config_data['hora_fin'],
        config_data['intervalo_consultas_minutos']
    )

    if not horas_disponibles:
        print("Error: No se pudieron generar las horas disponibles. Revise la configuración de hora_inicio, hora_fin e intervalo.")
        exit(1)

    print(f"Horas disponibles generadas: {horas_disponibles}")

    # Generar componentes del grafo
    nodos = generar_nodos(config_data, horas_disponibles)
    if not nodos:
        print("Error generando nodos. Verifique que haya pacientes, fases, consultas, médicos y horas disponibles.")
        exit(1)

    aristas = generar_aristas(nodos, map_paciente_info,duracion_consulta_minutos=config_data['intervalo_consultas_minutos'], horas_disponibles_str_list=horas_disponibles)

    # Use MinMaxGraph
    min_max_graph = MinMaxGraph(
        nodes=nodos,
        edges=aristas,
        pheromone_max=10.0,  # Valor máximo de feromonas (tau_max)
        pheromone_min=0.1,   # Valor minimo de feromonas (tau_min)
    )

    # Configurar y ejecutar MinMaxACO
    aco_minmax = MinMaxACO(
        graph=min_max_graph,
        config_data=config_data,
        horas_disponibles=horas_disponibles,
        n_ants=20, iterations=100, alpha=1.0, beta=3, rho=0.03, Q=1000.0
    )

    print("Ejecutando MinMaxACO...")
    best_solution, best_cost = aco_minmax.run()
    aco_minmax.plot_convergence()


    if best_solution:
        # Agrupar asignaciones por paciente
        asignaciones_por_paciente = defaultdict(list)
        for asignacion_tuple in best_solution:
            paciente = asignacion_tuple[0]
            asignaciones_por_paciente[paciente].append(asignacion_tuple)

        intervalo_global_min = config_data['intervalo_consultas_minutos']

        for paciente_id in sorted(asignaciones_por_paciente.keys()):
            asignaciones_paciente = asignaciones_por_paciente[paciente_id]
            print(f"\nPaciente: {paciente_id}")

            # Obtener información del estudio para el paciente
            info_estudio_paciente = aco_minmax.paciente_to_estudio.get(paciente_id)
            if info_estudio_paciente:
                print(f"  Estudio: {info_estudio_paciente['nombre_estudio']}")

                # Ordenar fases según el orden del estudio
                asignaciones_ordenadas = sorted(
                    asignaciones_paciente,
                    key=lambda asign_tuple: info_estudio_paciente['orden_fases'].get(asign_tuple[4], float('inf'))
                )

                for asign_tuple_ordenada in asignaciones_ordenadas:
                    _, consulta, hora, medico, fase = asign_tuple_ordenada
                    orden = info_estudio_paciente['orden_fases'].get(fase, "N/A")
                    duracion = intervalo_global_min
                    print(f"  {orden}. {fase} - {hora} ({duracion}min) - {consulta} - {medico}")
            else:
                print(f"  Info de estudio no encontrada para paciente {paciente_id}")

        print(f"\nCosto total (MinMaxACO): {best_cost:.2f}")
        if aco_minmax.execution_time is not None:
            print(f"Tiempo ejecución (MinMaxACO): {aco_minmax.execution_time:.2f}s")

        # Generar gráfico de Gantt
        if plot_gantt_chart:
            print("\nGenerando gráfico de Gantt (MinMaxACO)...")
            try:
                # Preparar datos para el gráfico
                fases_duration_para_gantt = {}
                all_configured_phase_names = set()

                for estudio_cfg in config_data['tipos_estudio']:
                    all_configured_phase_names.update(estudio_cfg['fases'])

                # Asignar duración global a todas las fases
                for phase_name in all_configured_phase_names:
                    fases_duration_para_gantt[phase_name] = intervalo_global_min

                # Lista completa de pacientes
                _pacientes_set = set()
                for estudio_cfg in config_data['tipos_estudio']:
                    _pacientes_set.update(estudio_cfg['pacientes'])
                lista_pacientes_completa = list(_pacientes_set)

                # Calcular horas de inicio y fin para el gráfico
                try:
                    plot_start_hour = datetime.strptime(config_data['hora_inicio'], "%H:%M").hour

                    latest_slot_start_str = horas_disponibles[-1]
                    latest_slot_start_dt_time = datetime.strptime(latest_slot_start_str, "%H:%M").time()

                    plot_end_hour_dt = datetime.combine(datetime.today(), latest_slot_start_dt_time) + timedelta(minutes=intervalo_global_min)

                    plot_end_hour_int = plot_end_hour_dt.hour
                    if plot_end_hour_dt.minute > 0:
                        plot_end_hour_int += 1

                    if plot_end_hour_int > 23:
                        plot_end_hour_int = 23

                    plot_end_hour = plot_end_hour_int

                except (ValueError, TypeError, IndexError) as e:
                    raise Exception(f"Error calculando horas para Gantt: {e}.")

                gantt_output_dir = "/app/plots/"
                os.makedirs(gantt_output_dir, exist_ok=True)
                gantt_filepath = os.path.join(gantt_output_dir, "gantt_plotly_schedule_MinMaxACO.png")

                plot_gantt_chart(
                    best_solution=best_solution,
                    fases_duration=fases_duration_para_gantt,
                    pacientes=lista_pacientes_completa,
                    medicos=config_data['medicos'],
                    consultas=config_data['consultas'],
                    output_filepath=gantt_filepath,
                    configured_start_hour=plot_start_hour,
                    configured_end_hour=plot_end_hour
                )
            except Exception as e:
                print(f"Error generando gráfico de Gantt: {e}")
                import traceback
                traceback.print_exc()
    else:
        print("\nNo se encontró solución válida (MinMaxACO).")
        if aco_minmax.execution_time is not None:
            print(f"Tiempo ejecución (MinMaxACO): {aco_minmax.execution_time:.2f}s")