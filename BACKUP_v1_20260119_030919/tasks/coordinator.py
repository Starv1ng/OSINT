# services/worker/tasks/coordinator.py
import time
import json
import asyncio
from sqlalchemy import create_engine, text
import os
import logging

# Importar la aplicación Celery
from .celery_app import app
# Importar el orquestador de módulos reales
from .orchestrator import ModuleOrchestrator
from .dynamic_orchestrator import DynamicModuleOrchestrator
# Importar el procesador de resultados y analizador de input
from .modules.utils.result_processor import ResultProcessor
from .modules.utils.input_analyzer import InputAnalyzer
# El indexado en Elasticsearch es gestionado por el orquestador para persistencia incremental

# Configurar logging
logger = logging.getLogger(__name__)

# Configurar conexión a la base de datos
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://dev:devpass@postgres:5432/osint")
engine = create_engine(DATABASE_URL)

# Instancias globales de orquestadores
module_orchestrator = ModuleOrchestrator()
dynamic_orchestrator = DynamicModuleOrchestrator(
    max_iterations=int(os.environ.get("MAX_ITERATIONS", "5")),
    relevance_threshold=float(os.environ.get("RELEVANCE_THRESHOLD", "0.5")),
    execution_mode=os.environ.get("EXECUTION_MODE", "normal")
)

@app.task(bind=True, name='process_osint_job')
def process_osint_job(self, job_id: str, search_data: dict):
    """
    Tarea REAL que procesa jobs OSINT usando módulos reales
    Ahora adapta dinámicamente los módulos según el tipo de input
    """
    query = search_data['value']
    logger.info(f"Procesando trabajo: {job_id}")
    logger.info(f"Entrada: {query}")
    
    try:
        # 1. ANALIZAR INPUT para determinar qué módulos usar
        input_analysis = InputAnalyzer.analyze(query)
        logger.info(f"Tipo detectado: {input_analysis['input_type']}")
        logger.info(f"Confianza: {input_analysis['confidence']:.2f}")
        logger.info(f"Módulos principales: {', '.join(input_analysis['primary_modules'])}")
        
        # 2. ACTUALIZAR ESTADO
        update_job_status(job_id, "processing")
        
        # 3. EJECUTAR BÚSQUEDA DINÁMICA CON MÓDULOS ADAPTADOS
        logger.info("Ejecutando búsqueda dinámica con módulos adaptados...")
        
        # Pasar información de análisis al orquestador
        search_data_enhanced = dict(search_data)
        search_data_enhanced['input_analysis'] = input_analysis
        search_data_enhanced['preferred_modules'] = input_analysis['primary_modules']
        
        results = asyncio.run(dynamic_orchestrator.execute_dynamic_search(job_id, search_data_enhanced))
        
        # 4. Procesar resultados (filtrado, evaluación, extracción)
        if results.get('findings'):
            processed = ResultProcessor.process_findings(
                results['findings'],
                query=query,
                context=input_analysis['input_type']
            )
            results['processed'] = processed
            logger.info(f"Procesados: {processed['statistics']['final_count']} hallazgos depurados")
            logger.info(
                f"Indicadores extraídos: {len(processed['extracted_indicators']['emails'])} correos, "
                f"{len(processed['extracted_indicators']['usernames'])} nombres de usuario"
            )
        
        # 5. GUARDAR RESULTADOS
        save_job_results(job_id, results)
        update_job_status(job_id, "completed")
        
        logger.info(f"Trabajo {job_id} completado")
        logger.info(f"Hallazgos: {len(results.get('findings', []))}")
        logger.info(f"Iteraciones: {results.get('iterations', 1)}")
        
        return {
            "job_id": job_id,
            "status": "completed",
            "input_type": input_analysis['input_type'],
            "findings_count": len(results.get('findings', [])),
            "processed_count": len(results.get('processed', {}).get('processed_findings', [])) if 'processed' in results else 0
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Job {job_id}: {e}")
        update_job_status(job_id, "failed")
        
        error_results = {
            "search_query": query,
            "search_type": search_data.get('input_type', 'unknown'),
            "findings": [],
            "error": str(e),
            "summary": {
                "total_findings": 0,
                "error": True,
                "error_message": str(e)
            }
        }
        save_job_results(job_id, error_results)
        
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(e)
        }


@app.task(bind=True, name='process_osint_job_dynamic')
def process_osint_job_dynamic(self, job_id: str, search_data: dict):
    """
    Tarea que procesa jobs OSINT con búsqueda dinámica iterativa
    """
    return process_osint_job(self, job_id, search_data)


@app.task(bind=True, name='process_osint_job_static')
def process_osint_job_static(self, job_id: str, search_data: dict):
    """
    Tarea que procesa jobs OSINT con búsqueda estática (módulos predefinidos)
    """
    logger.info(f"Procesando trabajo estático: {job_id}")
    logger.info(f"Búsqueda: {search_data['value']} (tipo: {search_data['input_type']})")
    
    try:
        update_job_status(job_id, "processing")
        
        logger.info("Ejecutando búsqueda OSINT estática...")
        results = asyncio.run(module_orchestrator.execute_search(job_id, search_data))

        save_job_results(job_id, results)
        update_job_status(job_id, "completed")

        logger.info(f"Trabajo {job_id} completado")
        logger.info(f"Resultados: {len(results.get('findings', []))} descubrimientos")

        return {
            "job_id": job_id,
            "status": "completed",
            "results_summary": results.get("summary", {})
        }
        
    except Exception as e:
        logger.error(f"Error procesando trabajo {job_id}: {e}")
        update_job_status(job_id, "failed")
        
        error_results = {
            "search_query": search_data["value"],
            "search_type": search_data["input_type"],
            "findings": [],
            "error": str(e),
            "summary": {
                "total_findings": 0,
                "error": True,
                "error_message": str(e)
            }
        }
        save_job_results(job_id, error_results)
        
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(e)
        }

def update_job_status(job_id: str, status: str):
    """Actualizar estado del job en PostgreSQL"""
    try:
        with engine.begin() as conn:
            query = text("UPDATE jobs SET status = :status WHERE job_id = :job_id")
            conn.execute(query, {"status": status, "job_id": job_id})
        logger.info(f"   BD: Job {job_id} -> {status}")
    except Exception as e:
        logger.error(f"Error actualizando estado: {e}")

def save_job_results(job_id: str, results: dict):
    """Guardar resultados en PostgreSQL"""
    try:
        # Guardar solo un resumen en Postgres. Los hallazgos completos están en Elasticsearch.
        summary = results.get('summary') if isinstance(results, dict) else None
        with engine.begin() as conn:
            query = text("UPDATE jobs SET result = :result WHERE job_id = :job_id")
            conn.execute(query, {"result": json.dumps({'summary': summary}), "job_id": job_id})
        logger.info(f"   BD: Resumen guardado para {job_id} (full results in ES)")
    except Exception as e:
        logger.error(f"Error guardando resultados: {e}")