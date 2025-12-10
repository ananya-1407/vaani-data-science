"""Module to interact with the LLM for the talk2bill pipeline"""
import traceback
from typing import Optional, Type, List, Dict, Any
import asyncio
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import fetch_env
from crons.talk2bill.vyapar.prompt_builder import Talk2BillPromptBuilder
from constants.talk2bill.vyapar.models import (
    IntentClassificationResponse,
    ExpenseModel,
    ExpenseMissingFieldsResponse,
    GenericQuestionAskResponse
)
from logger.logger import Logger

class LLMService:
    """
    LLMService class to interact with the LLM
    """
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model='gemini-2.0-flash',
            temperature=0.0,
            api_key=fetch_env("VYAPAR_T2B_API_KEY")
        )
        self.default_intent_response = IntentClassificationResponse(intent="other")
        self.default_expense_response = ExpenseModel()
        self.default_expense_missing_fields_response = ExpenseMissingFieldsResponse()
        self.default_generic_question_ask_response = GenericQuestionAskResponse()

    async def _invoke(
            self,
            prompt: str,
            response_format: Optional[Type[BaseModel]] = None,
            max_retries: int = 3,
            retry_delay: int = 1
        ) -> Optional[Type[BaseModel]]:
        """
        Invoke the LLM with the prompt and return the response

        Args:
            prompt: The prompt to invoke the LLM with
            response_format: The response format to return
            Optional[max_retries]: The maximum number of retries
            Optional[retry_delay]: The delay between retries
        Returns:
            Either a validated Pydantic model instance or a dictionary
        """
        last_exception = None

        for attempt in range(max_retries + 1):  # +1 because we want 3 retries total
            try:
                # response = await self.llm.ainvoke(prompt)
                structured_llm_json = self.llm.with_structured_output(
                    response_format,
                    method="json_schema"
                )
                response = await structured_llm_json.ainvoke(prompt)
                return response

            except Exception as e:
                last_exception = e

                if attempt < max_retries:  # Don't sleep on the last attempt
                    Logger.warn({
                        "message": f"LLM invoke failed on attempt {attempt + 1}, retrying in {retry_delay}s",
                        "tag": "LLMService",
                        "data": {
                            "error": str(e),
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "retry_delay": retry_delay
                        }
                    })
                    await asyncio.sleep(retry_delay)
                else:
                    Logger.warn({
                        "message": f"LLM invoke failed after {max_retries + 1} attempts",
                        "tag": "LLMService",
                        "data": {
                            "error": str(e),
                            "total_attempts": max_retries + 1,
                            "traceback": traceback.format_exc()
                        }
                    })

        # If we get here, all retries failed
        raise last_exception

    async def identify_intent(
        self,
        user_query: str,
        history: List[Dict]
    ) -> IntentClassificationResponse:
        """
        Identify the intent of the user query based on the history

        Args:
            user_query: The user query to identify the intent of
            history: The history of the conversation
        
        Returns:
            The identified intent
        """
        try:
            if not user_query:
                return self.default_intent_response
            Logger.info({
                "message": "Identifying intent",
                "tag": "VyaparTalk2Bill",
                "data": {
                    "user_query": user_query,
                }
            })
            prompt = Talk2BillPromptBuilder.build_intent_classification_prompt(history, user_query)
            intent_response = await self._invoke(prompt, IntentClassificationResponse)
            return intent_response
        except Exception as e:
            Logger.warn({
                "message": "Failed to identify intent",
                "tag": "VyaparTalk2Bill",
                "data": {
                    "user_query": user_query,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            })
            raise e

    async def extract_expense(
        self, user_query: str,
        latest_invoice: Dict[str, Any] = {},
        history: List[Dict] = []
    ) -> ExpenseModel:
        """
        Extract the expense from the user query based on the latest invoice

        Args:
            user_query: The user query to extract the expense from
            latest_invoice: The latest invoice to extract the expense from
            history: The last 10 messages of the conversation
        
        Returns:
            The extracted expense
        """
        try:
            Logger.info({
                "message": "Extracting expense",
                "tag": "VyaparTalk2Bill",
                "data": {
                    "user_query": user_query,
                }
            })
            if not user_query:
                return self.default_expense_response
            prompt = Talk2BillPromptBuilder.build_expense_extraction_prompt(
                user_query,
                latest_invoice,
                history
            )
            return await self._invoke(prompt, ExpenseModel)

        except Exception as e:
            Logger.warn({
                "message": "Failed to extract expense",
                "tag": "VyaparTalk2Bill",
                "data": {
                    "user_query": user_query,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            })
            raise e

    async def ask_question(
        self,
        user_query: str,
        intent: str,
        invoice: ExpenseModel = None,
        history: List[Dict] = []
    ):
        """
        Ask a question based on the intent and the invoice

        Args:
            user_query: The user query to ask a question about
            intent: The intent of the user query
            invoice: The invoice to ask a question about
            history: The history of the conversation

        Returns:
            The question response with status
            (GenericQuestionAskResponse or ExpenseMissingFieldsResponse)
        """
        try:

            if intent == "other":
                prompt = Talk2BillPromptBuilder.build_generic_question_ask_prompt(
                    user_query,
                    history
                )
                response: GenericQuestionAskResponse = await self._invoke(
                    prompt,
                    GenericQuestionAskResponse
                )
                return response

            if intent == "expense":
                prompt = Talk2BillPromptBuilder.build_expense_missing_fields_prompt(
                    invoice.model_dump(),
                    user_query,
                    history
                )
                response: ExpenseMissingFieldsResponse = await self._invoke(
                    prompt,
                    ExpenseMissingFieldsResponse
                )
                return response

            return self.default_generic_question_ask_response

        except Exception as e:
            Logger.warn({
                "message": "Failed to ask question",
                "tag": "VyaparTalk2Bill",
                "data": {
                    "user_query": user_query,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            })
            raise e
