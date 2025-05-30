import time
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os
from MinMax.MinMaxAco import MinMaxACO
from MinMax.MinMaxGraph import MinMaxGraph
from utils.generate_graph_components import generar_nodos, generar_aristas

def run_aco_with_params(alpha, beta, rho, Q, pheromone_max, pheromone_min, initial_pheromone, n_ants=20, iterations=100):
    """Run ACO with specific parameters and return the best cost."""
    # Configuración del problema médico
    pacientes = ['Paciente1', 'Paciente2', 'Paciente3', 'Paciente4', 'Paciente5']
    consultas = ['ConsultaA', 'ConsultaB', 'ConsultaC']
    horas = ['09:00', '10:00', '11:00', '12:00', '13:00', 
            '14:00', '15:00', '16:00', '17:00', '18:00']
    medicos = ['MedicoX', 'MedicoY', 'MedicoZ']
    fases = ['Fase1', 'Fase2', 'Fase3', 'Fase4']
    
    orden_fases = {'Fase1': 1, 'Fase2': 2, 'Fase3': 3, 'Fase4': 4}
    duracion_fases = {'Fase1': 60, 'Fase2': 60, 'Fase3': 60, 'Fase4': 60}

    # Generar componentes del grafo
    nodos = generar_nodos(pacientes, consultas, horas, medicos, fases)
    aristas = generar_aristas(nodos, orden_fases)

    # Configurar grafo con límites estáticos
    graph = MinMaxGraph(
        nodes=nodos,
        edges=aristas,
        pheromone_max=pheromone_max,
        pheromone_min=pheromone_min,
        initial_pheromone=initial_pheromone
    )

    # Configurar algoritmo MinMaxACO
    aco = MinMaxACO(
        graph=graph,
        fases_orden=orden_fases,
        fases_duration=duracion_fases,
        pacientes=pacientes,
        medicos=medicos,
        consultas=consultas,
        horas=horas,
        n_ants=n_ants,
        iterations=iterations,
        alpha=alpha,
        beta=beta,
        rho=rho,
        Q=Q
    )

    # Ejecutar optimización
    mejor_solucion, mejor_costo = aco.run()
    
    return mejor_costo, aco.execution_time

def plot_parameter_effects(df):
    """Visualizar el efecto de los parámetros en el costo."""
    fig, axs = plt.subplots(2, 2, figsize=(15, 10))
    
    # Efecto de alpha en el costo
    alpha_effect = df.groupby('alpha')['costo'].mean().reset_index()
    axs[0, 0].plot(alpha_effect['alpha'], alpha_effect['costo'], 'o-')
    axs[0, 0].set_title('Efecto de Alpha en el Costo')
    axs[0, 0].set_xlabel('Alpha')
    axs[0, 0].set_ylabel('Costo Promedio')
    
    # Efecto de beta en el costo
    beta_effect = df.groupby('beta')['costo'].mean().reset_index()
    axs[0, 1].plot(beta_effect['beta'], beta_effect['costo'], 'o-')
    axs[0, 1].set_title('Efecto de Beta en el Costo')
    axs[0, 1].set_xlabel('Beta')
    axs[0, 1].set_ylabel('Costo Promedio')
    
    # Efecto de rho en el costo
    rho_effect = df.groupby(pd.cut(df['rho'], bins=5))['costo'].mean().reset_index()
    axs[1, 0].plot(range(len(rho_effect)), rho_effect['costo'], 'o-')
    axs[1, 0].set_title('Efecto de Rho en el Costo')
    axs[1, 0].set_xlabel('Rho (Bins)')
    axs[1, 0].set_ylabel('Costo Promedio')
    
    # Efecto de Q en el costo
    # Since Q is now an integer in a wider range, use bins for visualization
    Q_effect = df.groupby(pd.cut(df['Q'], bins=5))['costo'].mean().reset_index()
    axs[1, 1].plot(range(len(Q_effect)), Q_effect['costo'], 'o-')
    axs[1, 1].set_title('Efecto de Q en el Costo')
    axs[1, 1].set_xlabel('Q (Bins)')
    axs[1, 1].set_ylabel('Costo Promedio')
    
    plt.tight_layout()
    
    # Ensure directory exists for the plot
    os.makedirs('/app/hpo/minmax', exist_ok=True)
    plt.savefig('/app/hpo/minmax/parameter_effects.png')
    plt.show()

def random_search_hpo(n_iterations=50, n_ants=20, aco_iterations=500):
    """Perform random search hyperparameter optimization."""
    # Definir espacios de búsqueda para cada parámetro
    param_ranges = {
        'rho': (0.01, 0.5),
        'Q': (1, 200000),  # Integer values
        'pheromone_max': (10.0, 1000.0),
        'pheromone_min': (0.01, 100.0),
        'initial_pheromone': (10.0, 200.0)
    }
    
    # Almacenar resultados
    results = []
    
    # Ensure directory exists
    os.makedirs('/app/hpo/minmax', exist_ok=True)
    
    # Iniciar el tiempo
    start_time = time.time()
    
    # Realizar random search
    for i in range(n_iterations):
        print(f"Iteración {i+1}/{n_iterations} - Tiempo transcurrido: {time.time() - start_time:.2f}s")
        
        # Generar parámetros aleatorios
        rho = np.random.uniform(param_ranges['rho'][0], param_ranges['rho'][1])
        # Q is now an integer
        Q = np.random.randint(param_ranges['Q'][0], param_ranges['Q'][1] + 1)
        pheromone_max = np.random.uniform(param_ranges['pheromone_max'][0], param_ranges['pheromone_max'][1])
        pheromone_min = np.random.uniform(param_ranges['pheromone_min'][0], param_ranges['pheromone_min'][1])
        
        # Asegurarse de que pheromone_min < pheromone_max
        if pheromone_min >= pheromone_max:
            pheromone_min, pheromone_max = pheromone_max * 0.1, pheromone_max
        
        initial_pheromone = np.random.uniform(param_ranges['initial_pheromone'][0], param_ranges['initial_pheromone'][1])
        
        # Asegurarse de que initial_pheromone <= pheromone_max
        if initial_pheromone > pheromone_max:
            initial_pheromone = pheromone_max
        
        try:
            # Ejecutar ACO con los parámetros actuales y n_ants fijo
            costo, tiempo_ejecucion = run_aco_with_params(
                1, 3, rho, Q,
                pheromone_max, pheromone_min, initial_pheromone,
                n_ants=n_ants, iterations=aco_iterations
            )
            
            # Almacenar resultados
            results.append({
                'alpha': 1.0,
                'beta': 3.0,
                'rho': rho,
                'Q': Q,
                'pheromone_max': pheromone_max,
                'pheromone_min': pheromone_min,
                'initial_pheromone': initial_pheromone,
                'costo': costo,
                'tiempo': tiempo_ejecucion
            })
            
            # Guardar resultados parciales
            if (i+1) % 5 == 0:
                df = pd.DataFrame(results)
                df.to_csv('/app/hpo/minmax/aco_random_hpo_results_partial.csv', index=False)
                
        except Exception as e:
            print(f"Error con la combinación {i+1}: {str(e)}")
    
    # Convertir resultados a DataFrame
    df_results = pd.DataFrame(results)
    
    # Guardar todos los resultados
    df_results.to_csv('/app/hpo/minmax/aco_random_hpo_results.csv', index=False)
    
    # Ordenar por costo (mejor primero)
    df_sorted = df_results.sort_values('costo')
    
    # Mostrar los mejores resultados
    print("\n● Top 5 mejores configuraciones:")
    print(df_sorted.head(5))
    
    # Devolver los mejores parámetros
    best_params = df_sorted.iloc[0].to_dict()
    return best_params

def main():
    print("ACO Hyperparameter Optimization - Random Search")
    n_iterations = int(input("Ingrese el número de iteraciones para Random Search: "))
    n_ants = int(input("Ingrese el número de hormigas para ACO: "))
    aco_iterations = int(input("Ingrese el número de iteraciones para el algoritmo ACO: "))
    
    print("\nIniciando Random Search HPO...")
    best_params = random_search_hpo(n_iterations, n_ants, aco_iterations)
    
    print("\n● Mejores parámetros encontrados:")
    for param, value in best_params.items():
        if param not in ['costo', 'tiempo']:  # Excluir métricas
            print(f"  - {param}: {value}")
    
    print(f"\n● Mejor costo: {best_params['costo']:.2f}")
    print(f"● Tiempo de ejecución: {best_params['tiempo']:.2f}s")

if __name__ == "__main__":
    main()