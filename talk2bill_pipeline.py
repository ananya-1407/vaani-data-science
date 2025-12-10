"""Module to run the talk2bill pipeline"""
import traceback
from datetime import datetime, timezone
import asyncio
from typing import List, Dict
from crons.talk2bill.vyapar.llm_service import LLMService
from constants.talk2bill.vyapar.status import Talk2BillStatus
from constants.talk2bill.vyapar.models import (
    PipelineResponse,
    ExpenseModel,
    ConversationStatus
)
from logger.logger import Logger
from db.mongo.vyapar.talk2bill_repository import Talk2BillRepository
from models.talk2bill.vyapar import Talk2BillModel as VyaparTalk2BillModel

TALK2BILL_PIPELINE_INSTANCE = None

class Talk2BillPipeline:
    """
    Talk2BillPipeline class to run the talk2bill pipeline
    """
    def __init__(self):
        self.llm_service = None
        self._initialized = False

    async def initialize(self):
        """
        Initialize the talk2bill pipeline
        """
        if not self._initialized:
            self.llm_service = LLMService()
            self._initialized = True

    @classmethod
    async def create(cls):
        """
        Create the instance of the talk2bill pipeline
        """
        instance = cls()
        await instance.initialize()
        return instance

    @classmethod
    async def get_instance(cls):
        """
        Get the instance of the talk2bill pipeline
        """
        global TALK2BILL_PIPELINE_INSTANCE
        if not TALK2BILL_PIPELINE_INSTANCE:
            TALK2BILL_PIPELINE_INSTANCE = await cls.create()
        return TALK2BILL_PIPELINE_INSTANCE

    async def get_session_history(self, session_id: str, limit: int = 5) -> List[Dict]:
        """
        Get the session history from the mongo collection

        Args:
            session_id: The session id
            limit: The limit on the number of documents to search in mongo collection

        Returns:
            The session history
        """
        documents = await Talk2BillRepository.find_all_processed_invoices_by_session_with_limit(
            session_id,
            limit
        )
        history = []

        for doc in documents:
            history.append({
            "user": doc.get("transcription", ""),
            "model": doc.get("modelQuestion", "")
        })

        return history


    async def pipeline(self, talk2bill_job: VyaparTalk2BillModel) -> PipelineResponse:
        """
        Pipeline for the talk2bill job

        Args:
            talk2bill_job: The talk2bill job

        Returns:
            The pipeline response
        """
        ref_id = None
        try:
            user_query = talk2bill_job.transcription
            session_id = talk2bill_job.sessionId
            ref_id = talk2bill_job.fileRefId

            latest_history, latest_invoice = await asyncio.gather(
                self.get_session_history(session_id, 5),
                Talk2BillRepository.find_latest_processed_invoice_by_session(session_id)
            )
            # Identify the intent of the user
            intent_response = await self.llm_service.identify_intent(user_query, latest_history)
            intent = intent_response.intent
            invoice = ExpenseModel()
            conversation_status = ConversationStatus.CONTINUE.value

            if intent == "expense":
                # Extract the expense from the user query
                invoice = await self.llm_service.extract_expense(
                    user_query,
                    latest_invoice,
                    latest_history
                )

                # Convert the item amounts and quantities to positive values
                if invoice.items:
                    for item in invoice.items:
                        if item.item_amount is not None and item.item_amount < 0:
                            item.item_amount = abs(item.item_amount)
                        if item.item_qty is not None and item.item_qty < 0:
                            item.item_qty = abs(item.item_qty)

                # Ask a question based on the intent and the invoice
                question_response = await self.llm_service.ask_question(
                    user_query,
                    intent,
                    invoice=invoice,
                    history=latest_history
                )
                question = question_response.question
                conversation_status = question_response.status.value
            else:
                # Ask a question based on the intent and the history
                question_response = await self.llm_service.ask_question(
                    user_query,
                    intent,
                    history=latest_history
                )
                question = question_response.question
                conversation_status = question_response.status.value

            if conversation_status == ConversationStatus.COMPLETE.value:
                status = Talk2BillStatus.INVOICE_READY.value
            else:
                status = Talk2BillStatus.T2I_COMPLETED.value

            # Update the mongo collection with the invoice and the question
            result = await Talk2BillRepository.update_job(talk2bill_job, {
                "status": status,
                "invoice": invoice.model_dump(),
                "modelQuestion": question,
                "conversationStatus": conversation_status,
                "intent": intent,
                "updatedAt": datetime.now(timezone.utc)
            })

            print("Result of updating job:", result)
            # Return the pipeline response
            return PipelineResponse(question=question, invoice=invoice, status=conversation_status)

        except Exception as e:
            Logger.warn({
                "message": "Failed talk2bill-vyp pipeline",
                "tag": "VyaparTalk2Bill",
                "data": {
                    "ref_id": ref_id,
                    "session_id": session_id,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            })

            await Talk2BillRepository.update_job(talk2bill_job, {
                "status": Talk2BillStatus.FAILED.value,
                "updatedAt": datetime.now(timezone.utc),
                "errorReason": str(e)
            })
            raise e
