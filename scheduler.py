"""Module to schedule the talk2bill pipeline"""
import threading
import asyncio
import time
from dotenv import load_dotenv
from db.mongo.vyapar.talk2bill_repository import Talk2BillRepository
from logger.logger import Logger
from .talk2bill_pipeline import Talk2BillPipeline
from models.talk2bill.vyapar import Talk2BillModel
load_dotenv()

TALK2BILL_PIPELINE = None

async def process_document(document: Talk2BillModel):
    """
    Process a single document through the pipeline
    """
    Logger.info({
        "message": "Processing document",
        "tag": "VyaparTalk2Bill",
        "data": {
            "session_id": document.sessionId,
            "ref_id": document.fileRefId
        }
    })

    result = await TALK2BILL_PIPELINE.pipeline(document)
    Logger.info({
        "message": "Result of pipeline",
        "tag": "VyaparTalk2Bill",
        "data": {
            "result": result.model_dump(mode="json")
        }
    })

    Logger.info({
        "message": "Document processed",
        "tag": "VyaparTalk2Bill",
        "data": {
            "session_id": document.sessionId,
            "ref_id": document.fileRefId
        }
    })

    return result

async def main():
    """
    Main function to schedule the talk2bill pipeline
    """
    global TALK2BILL_PIPELINE
    thread_id = threading.get_ident()
    start_time = time.time()
    Logger.info({
        "message": "Starting Invoice Generation batch",
        "tag": "VyaparTalk2Bill",
        "data": {
            "thread_id": thread_id,
            "start_time": start_time
        }
    })
    results = []
    try:
        if TALK2BILL_PIPELINE is None:
            TALK2BILL_PIPELINE = await Talk2BillPipeline.get_instance()

        docs = await Talk2BillRepository.get_batch_of_jobs()

        results = await asyncio.gather(*[process_document(document) for document in docs])

    finally:
        Logger.info({
            "message": "Invoice Generation batch completed",
            "tag": "VyaparTalk2Bill",
            "data": {
                "docs_processed": len(results),
            }
        })
