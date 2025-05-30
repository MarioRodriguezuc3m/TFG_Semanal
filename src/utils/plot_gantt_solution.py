import plotly.figure_factory as ff
import pandas as pd
from datetime import datetime, timedelta
import os
import colorsys



def generate_hsv_distinct_colors(n_colors):
    """Genera n colores usando el espacio HSV con máxima separación de matiz"""
    colors = []
    for i in range(n_colors):
        hue = i / n_colors
        saturation = 0.8 + (i % 2) * 0.2
        value = 0.8 + (i % 3) * 0.1
        
        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        rgb_255 = tuple(int(c * 255) for c in rgb)
        colors.append(f'rgb({rgb_255[0]},{rgb_255[1]},{rgb_255[2]})')
    
    return colors



def create_phase_color_mapping(all_phase_names):
    """Crea un mapeo completo de fases a colores distintos usando HSV"""
    distinct_colors = generate_hsv_distinct_colors(len(all_phase_names))
    color_mapping = {}
    
    for i, phase_name in enumerate(sorted(all_phase_names)):
        color_mapping[phase_name] = distinct_colors[i]
    
    return color_mapping

def plot_gantt_chart(best_solution, fases_duration, pacientes, medicos, consultas, 
                     output_filepath='/app/plots/schedule_gantt.png',
                     configured_start_hour=8, 
                     configured_end_hour=20):  
    """
    Crea gráfico Gantt de la solución ACO usando Plotly
    """
    save_dir = os.path.dirname(output_filepath)
    if save_dir and not os.path.exists(save_dir):
        os.makedirs(save_dir, exist_ok=True)
    
    gantt_data = []
    base_date = datetime.today().date()
    
    default_fallback_color = 'rgb(128, 128, 128)' 

    actual_min_start_dt = None
    actual_max_end_dt = None

    for assignment in best_solution:
        patient, consultation, start_time_str, doctor, phase = assignment
        
        try:
            hour, minute = map(int, start_time_str.split(':'))
            start_dt = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
            
            duration_minutes = fases_duration.get(phase) 
            if duration_minutes is None:
                continue

            end_dt = start_dt + timedelta(minutes=duration_minutes)
            
            if actual_min_start_dt is None or start_dt < actual_min_start_dt:
                actual_min_start_dt = start_dt
            if actual_max_end_dt is None or end_dt > actual_max_end_dt:
                actual_max_end_dt = end_dt

            start_str_plotly = start_dt.strftime('%Y-%m-%d %H:%M:%S')
            end_str_plotly = end_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            hover_text = (f"<b>{patient} - {phase}</b><br>"
                          f"Médico: {doctor}<br>"
                          f"Consulta: {consultation}<br>"
                          f"Hora: {start_time_str} - {end_dt.strftime('%H:%M')}<br>"
                          f"Duración: {duration_minutes} min")
            
            gantt_data.append({'Task': f"{patient}", 'Start': start_str_plotly, 'Finish': end_str_plotly, 'Resource': phase, 'Description': hover_text})
            gantt_data.append({'Task': f"{doctor}", 'Start': start_str_plotly, 'Finish': end_str_plotly, 'Resource': phase, 'Description': hover_text})
            gantt_data.append({'Task': f"{consultation}", 'Start': start_str_plotly, 'Finish': end_str_plotly, 'Resource': phase, 'Description': hover_text})
        
        except (ValueError, TypeError):
            continue

    if not gantt_data:
        return None
    
    df = pd.DataFrame(gantt_data)
    task_order_prefix = {"Paciente:": 0, "Médico:": 1, "Consulta:": 2}
    df['Task_Sort_Key'] = df['Task'].apply(lambda x: (task_order_prefix.get(x.split(' ')[0] + ' ', 3), x))
    df = df.sort_values(by=['Task_Sort_Key', 'Start'])
    df = df.drop(columns=['Task_Sort_Key'])
    
    unique_resources_in_df = df['Resource'].unique()
    
    colors_for_plot = create_phase_color_mapping(unique_resources_in_df)

    fig = ff.create_gantt(
        df,
        colors=colors_for_plot, 
        index_col='Resource', 
        show_colorbar=True,
        group_tasks=True,     
        showgrid_x=True,
        showgrid_y=True,
        title='Cronograma de Citas Médicas',
        height=max(600, len(df['Task'].unique()) * 25), 
        width=1200,
        bar_width=0.4
    )
    
    for trace in fig.data:
        descriptions_for_trace = df[df['Resource'] == trace.name]['Description']
        trace["opacity"] = 0.5
        if not descriptions_for_trace.empty:
             trace.text = descriptions_for_trace.tolist()
        trace.hoverinfo = 'text'

    # Configurar rango del eje X
    x_axis_start_dt = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=configured_start_hour)
    x_axis_end_dt = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=configured_end_hour)

    # Expandir si hay datos fuera del rango configurado
    if actual_min_start_dt and actual_min_start_dt < x_axis_start_dt:
        x_axis_start_dt = actual_min_start_dt.replace(minute=0, second=0) 
    if actual_max_end_dt and actual_max_end_dt > x_axis_end_dt:
        x_axis_end_dt = (actual_max_end_dt.replace(minute=0, second=0) + timedelta(hours=1))

    time_ticks_values = []
    time_ticks_text = []
    current_tick_dt = x_axis_start_dt
    while current_tick_dt <= x_axis_end_dt:
        time_ticks_values.append(current_tick_dt.strftime('%Y-%m-%d %H:%M:%S'))
        time_ticks_text.append(current_tick_dt.strftime('%H:%M'))
        current_tick_dt += timedelta(hours=1)
    
    fig.update_layout(
        xaxis_title="Hora del Día",
        yaxis_title="Recursos (Pacientes, Médicos, Consultas)",
        legend_title="Fases del Estudio",
        font=dict(size=10),
        xaxis=dict(
            tickvals=time_ticks_values,
            ticktext=time_ticks_text,
            tickmode='array',
            range=[x_axis_start_dt.strftime('%Y-%m-%d %H:%M:%S'), 
                   x_axis_end_dt.strftime('%Y-%m-%d %H:%M:%S')]
        )
    )
    
    try:
        fig.write_image(output_filepath, scale=1.5)
    except Exception:
        return None
        
    return output_filepath