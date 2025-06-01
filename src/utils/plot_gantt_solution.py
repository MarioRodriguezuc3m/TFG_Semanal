import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import os
import colorsys
from collections import defaultdict
from datetime import datetime
import math

def generate_hsv_distinct_colors(n_colors):
    """Genera colores distintos usando HSV"""
    colors = []
    if n_colors == 0:
        return colors
    for i in range(n_colors):
        hue = i / n_colors
        saturation = 0.8 + (i % 2) * 0.2
        value = 0.8 + ((i // 2) % 2) * 0.1
        
        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        hex_color = mcolors.to_hex(rgb)
        colors.append(hex_color)
    return colors

def create_phase_color_mapping(all_phase_names):
    """Mapea cada fase a un color único"""
    sorted_phases = sorted(list(all_phase_names))
    distinct_colors = generate_hsv_distinct_colors(len(sorted_phases))
    color_mapping = {}
    
    for i, phase_name in enumerate(sorted_phases):
        color_mapping[phase_name] = distinct_colors[i]
    
    return color_mapping

def plot_gantt_chart(
    best_solution: list, 
    fases_duration_map: dict, 
    map_paciente_info: dict,
    output_filepath: str,
    num_dias_planificacion: int,
    configured_start_hour: int, 
    configured_end_hour: int
):
    """
    Genera gráfico Gantt para todos los pacientes
    """
    if not best_solution:
        return None

    output_dir = os.path.dirname(output_filepath)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Obtener todas las fases y crear mapeo de colores
    all_phases_in_solution = set(item[5] for item in best_solution)
    all_phases_from_config = set(fases_duration_map.keys())
    comprehensive_phase_list = sorted(list(all_phases_in_solution.union(all_phases_from_config)))
    phase_color_map = create_phase_color_mapping(comprehensive_phase_list)

    # Preparar datos para el plot
    plot_data = []
    all_known_patients = sorted(list(map_paciente_info.keys()))
    if not all_known_patients:
        all_known_patients = sorted(list(set(item[0] for item in best_solution)))
    patient_to_y_coord = {patient_id: i for i, patient_id in enumerate(all_known_patients)}

    # Configuración del eje X comprimido
    hours_in_working_day_on_plot = float(configured_end_hour - configured_start_hour)
    if hours_in_working_day_on_plot <= 0:
        hours_in_working_day_on_plot = 8.0  # Default 8 horas
    
    gap_between_days_on_plot_hrs = 1.5  # Separación visual entre días
    max_plot_x = 0

    # Procesar cada asignación
    for assignment in best_solution:
        patient_id, _, dia_idx, hora_str, _, phase_name = assignment
        duration_minutes = fases_duration_map.get(phase_name)
        if duration_minutes is None: 
            continue

        y_coord = patient_to_y_coord.get(patient_id)
        if y_coord is None: 
            continue
            
        try:
            time_obj = datetime.strptime(hora_str, "%H:%M").time()
            start_hour_decimal_in_day = time_obj.hour + time_obj.minute / 60.0

            # Calcular posición relativa dentro del día de trabajo
            relative_start_offset_in_day = max(0, start_hour_decimal_in_day - configured_start_hour)
            plot_x_day_base = dia_idx * (hours_in_working_day_on_plot + gap_between_days_on_plot_hrs)
            
            plot_x_start = plot_x_day_base + relative_start_offset_in_day
            duration_hours = duration_minutes / 60.0
            plot_x_end = plot_x_start + duration_hours
            
            max_plot_x = max(max_plot_x, plot_x_end)
            plot_data.append((y_coord, patient_id, phase_name, plot_x_start, plot_x_end))
        except ValueError:
            continue
    
    if not plot_data:
        return None
        
    # Crear figura
    num_patients = len(all_known_patients)
    fig_height = max(6, num_patients * 0.6) 
    fig, ax = plt.subplots(figsize=(16, fig_height))

    ax.set_title("Cronograma de Actividades por Paciente")
    plotted_labels_for_legend = set()

    # Dibujar las actividades
    for y_coord, _, phase_name, plot_x_start, plot_x_end in plot_data:
        color = phase_color_map.get(phase_name, 'gray')
        ax.plot([plot_x_start, plot_x_end], [y_coord, y_coord], 
                marker='o', color=color, linewidth=3, markersize=6,
                label=phase_name if phase_name not in plotted_labels_for_legend else "_nolegend_")
        plotted_labels_for_legend.add(phase_name)

    # Configurar eje Y (pacientes)
    ax.set_yticks(range(num_patients))
    ax.set_yticklabels(all_known_patients)
    ax.set_ylabel("Paciente")
    if num_patients > 0:
        ax.set_ylim(-0.5, num_patients - 0.5)

    # Configurar eje X (tiempo)
    ax.set_xlabel("Tiempo (Día - Hora)")
    x_ticks = []
    x_tick_labels = []
    hour_tick_interval = 2 if hours_in_working_day_on_plot > 4 else 1

    # Calcular ticks del eje X
    for d_idx in range(num_dias_planificacion):
        # Calcular el inicio del día en el eje X
        plot_x_day_base = d_idx * (hours_in_working_day_on_plot + gap_between_days_on_plot_hrs)
        # Calcular ticks para cada hora del día
        for h_offset in range(0, int(hours_in_working_day_on_plot) + 1, hour_tick_interval):
            actual_hour = configured_start_hour + h_offset
            if actual_hour > configured_end_hour:
                break # No agregar ticks fuera del rango configurado
            
            tick_plot_x = plot_x_day_base + h_offset
            x_ticks.append(tick_plot_x)
            x_tick_labels.append(f"D{d_idx+1} {actual_hour:02d}:00")
    
    # Fallback si no hay ticks
    if not x_ticks:
        x_ticks.append(0)
        x_tick_labels.append(f"D1 {configured_start_hour:02d}:00")
        if hours_in_working_day_on_plot > 0:
            x_ticks.append(hours_in_working_day_on_plot)
            x_tick_labels.append(f"D1 {configured_end_hour:02d}:00")

    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_tick_labels, rotation=45, ha="right", fontsize=9)
    
    # Configurar límites del eje X
    min_xlim = -0.5 
    overall_plot_width_all_days = (num_dias_planificacion -1) * (hours_in_working_day_on_plot + gap_between_days_on_plot_hrs) + hours_in_working_day_on_plot
    max_xlim = max(max_plot_x, overall_plot_width_all_days) + 0.5
    ax.set_xlim(min_xlim, max_xlim)
    
    # Grid
    ax.grid(True, which='major', axis='x', linestyle='-', linewidth=0.5, alpha=0.7)
    ax.grid(True, which='major', axis='y', linestyle=':', linewidth=0.5, alpha=0.7)
    
    # Leyenda
    handles = []
    labels = []
    for phase_name_in_legend in comprehensive_phase_list:
        color = phase_color_map.get(phase_name_in_legend, 'gray')
        line = plt.Line2D([0], [0], marker='o', color=color, linewidth=3, markersize=6, label=phase_name_in_legend)
        handles.append(line)
        labels.append(phase_name_in_legend)

    ax.legend(handles, labels, loc='upper left', bbox_to_anchor=(1.01, 1.02), borderaxespad=0., fontsize='small')
    plt.tight_layout(rect=[0, 0, 0.86, 0.98])

    # Guardar
    try:
        plt.savefig(output_filepath, dpi=150)
    except Exception as e:
        plt.close(fig)
        return None
    
    plt.close(fig)
    return output_filepath