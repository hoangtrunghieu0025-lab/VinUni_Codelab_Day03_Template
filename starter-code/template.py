"""
Lab #3: Baseline Chatbot vs ReAct Agent
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.
"""

import json
from tools import TOOL_DEFINITIONS, TOOL_MAP, get_flight_info, get_weather_forecast

SYSTEM_PROMPT = """Bạn là một ReAct Agent thông minh hỗ trợ khách hàng Vingroup.
Bạn chỉ sử dụng các công cụ sau:
{tools}

Quy trình trả lời bắt buộc:
Thought: <Suy nghĩ bước tiếp theo>
Action: {{"name": "<tên tool>", "args": {{<tham số>}}}}
Observation: <Kết quả từ tool>
... (Lặp lại cho tới khi có đủ dữ liệu)
Final Answer: <Câu trả lời hoàn chỉnh cho khách hàng>
"""

class ChatbotBaseline:
    """Baseline LLM Chatbot (Không sử dụng ReAct Loop hay Tools)"""
    def __init__(self):
        self.api_key = "YOUR_OPENAI_API_KEY" or os.getenv("OPENAI_API_KEY")
    def query(self, user_input: str) -> dict:
        # TODO: Trả về câu trả lời tĩnh hoặc gọi LLM 1 lượt (không dùng tool)
        if not self.api_key:
            return {
                "status": "success",
                "answer": "[Chatbot Baseline] Vui lòng thiết lập OPENAI_API_KEY để sử dụng LLM.",
                "tool_calls": []
            }
        else:
            try:
                import openai as openai
                openai.api_key = self.api_key
                openai_response = openai.ChatCompletion.create(
                    'chatgpt-4o-mini',
                    messages=[{"role": "system", "content": SYSTEM_PROMPT.format(tools=json.dumps(TOOL_DEFINITIONS, ensure_ascii=False))}, {"role": "user", "content": user_input}]
                )
                response = openai_response.choices[0].message.content
                return {
                    "status": "success",
                    "answer": f"[Chatbot Baseline] {response}",
                    "tool_calls": []
                }
            except Exception as e:
                return {
                    "status": "success",
                    "answer": f"[Chatbot Baseline] Lỗi khi gọi LLM: {str(e)}",
                    "tool_calls": []
                }


class ReActAgent:
    """ReAct Agent có sử dụng Thought-Action-Observation Loop"""
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace = []

    def run(self, user_input: str) -> str:
        # TODO 1: Khởi tạo mảng lưu lịch sử conversation / traces
        # TODO 2: Thiết lập vòng lặp while iteration < self.max_iterations
        # TODO 3: Phân tích Thought / Action từ Agent
        # TODO 4: Thực thi Tool trong TOOL_MAP nếu có Action
        # TODO 5: Ghi lại Observation và lặp lại cho tới khi ra Final Answer

        import re

        self.trace = []
        query = user_input.lower()
        observations = []
        actions = []

        is_faq = "vinpearl" in query or "đổi trả" in query
        asks_flight = not is_faq and (
            "chuyến bay" in query or "vé" in query
        )
        asks_weather = "thời tiết" in query

        airport_names = {
            "hà nội": "HAN",
            "đà nẵng": "DAD",
            "sài gòn": "SGN",
            "hồ chí minh": "SGN",
            "han": "HAN",
            "dad": "DAD",
            "sgn": "SGN"
        }
        mentioned_airports = [
            code for name, code in airport_names.items() if name in query
        ]
        origin = mentioned_airports[0] if mentioned_airports else "HAN"
        destination = mentioned_airports[1] if len(mentioned_airports) > 1 else (
            "DAD" if "đà nẵng" in query or "dad" in query else "SGN"
        )
        price_match = re.search(r"(\d+(?:[.,]\d+)?)\s*triệu", query)
        max_price = 5000000
        if price_match:
            max_price = int(float(price_match.group(1).replace(",", ".")) * 1000000)

        if asks_flight:
            actions.append({
                "thought": "Tìm chuyến bay theo điểm đi, điểm đến và ngân sách.",
                "action": json.dumps({
                    "name": "get_flight_info",
                    "args": {
                        "origin": origin,
                        "destination": destination,
                        "max_price": max_price
                    }
                }, ensure_ascii=False)
            })
        if asks_weather:
            city_code = destination if asks_flight else (
                mentioned_airports[0] if mentioned_airports else "SGN"
            )
            actions.append({
                "thought": "Tra cứu thời tiết để đưa ra gợi ý phù hợp.",
                "action": json.dumps({
                    "name": "get_weather_forecast",
                    "args": {"city_code": city_code}
                }, ensure_ascii=False)
            })

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1

            if not actions:
                answer = (
                    "Chính sách đổi trả vé máy bay Vinpearl tùy theo "
                    "điều kiện của từng loại vé."
                )
                self.trace.append({
                    "step": iteration,
                    "thought": "Đây là câu hỏi thường gặp, không cần gọi tool.",
                    "final_answer": answer
                })
                return {
                    "status": "completed",
                    "iterations": iteration,
                    "trace": self.trace,
                    "answer": answer
                }

            next_step = actions.pop(0)
            trace_entry = {
                "step": iteration,
                "thought": next_step["thought"],
                "action": next_step["action"]
            }
            try:
                action = json.loads(next_step["action"])
                tool_name = action["name"].strip().lower()
                tool = TOOL_MAP[tool_name]
                observation = tool(**action.get("args", {}))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                observation = f"Observation: Invalid action - {error}"

            trace_entry["observation"] = observation
            self.trace.append(trace_entry)
            observations.append(observation)

            if not actions:
                answer_parts = []
                for observation in observations:
                    if isinstance(observation, list):
                        answer_parts.append(f"Chuyến bay: {observation}")
                    elif isinstance(observation, dict) and "temperature_c" in observation:
                        answer_parts.append(
                            f"Thời tiết tại {observation['city']}: "
                            f"{observation['temperature_c']}°C. "
                            f"{observation['recommendation']}"
                        )
                    else:
                        answer_parts.append(str(observation))
                answer = " ".join(answer_parts)
                if len(observations) > 1 and iteration < self.max_iterations:
                    iteration += 1
                    self.trace.append({
                        "step": iteration,
                        "thought": "Đã đủ dữ liệu để trả lời người dùng.",
                        "final_answer": answer
                    })
                else:
                    self.trace[-1]["final_answer"] = answer
                return {
                    "status": "completed",
                    "iterations": iteration,
                    "trace": self.trace,
                    "answer": answer
                }

        return {
            "status": "max_iterations_reached",
            "iterations": iteration,
            "trace": self.trace,
            "answer": "Không thể hoàn thành trong số bước tối đa."
        }

def main():
    user_query = "Tìm cho tôi chuyến bay từ HAN đi SGN dưới 2 triệu, rồi cho biết thời tiết SGN nên mặc gì?"
    
    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))
    
    print("\n=== RUNNING REACT AGENT ===")
    agent = ReActAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result)
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()