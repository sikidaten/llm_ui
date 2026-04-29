import base64

# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


from openai import OpenAI

def chat_with_gpt(message: str, images=None) -> str:
    # print(f"Message: {message}")
    """
    Send a message (and optional images) to ChatGPT and get a response.
    Args:
        message: The user message to send
        images: List of image URLs (optional)
    Returns:
        The assistant's response
    """
    with open("api.key", "r") as f:
        api_key = f.read().strip()
    client = OpenAI(
        api_key=api_key
    )
    # Build the input structure as in the JS example
    content = [
        {"type": "input_text", "text": message}
    ]
    if images:
        for image in images:
            img_url = encode_image(image)
            content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{img_url}"})
    response = client.responses.create(
        model="gpt-5.4",
        reasoning={'effort': 'none'},
        input=[
            {
                "role": "user",
                "content": content
            }
        ],
    )
    print(response.output_text)
    # time.sleep(2)
    print("========================================")
    return response.output_text

def test_chat_with():
    response = chat_with_gpt("read the image", images=["./test.png"])
    print(response)

def chat_with_gemini(content):
    from google import genai
    api="AIzaSyAEFn_xchv_W9LQ1N3a65-iFYw_JbN2PhE"

    client = genai.Client(api_key=api)

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=content,
    )
    print(response.text)

def chat_with_gemini_with_link():
    from google import genai
    from google.genai.types import Tool, GenerateContentConfig

    api="AIzaSyAEFn_xchv_W9LQ1N3a65-iFYw_JbN2PhE"
    client = genai.Client(api_key=api)
    model_id = "gemini-3-flash-preview"

    tools = [
    {"url_context": {}},
    ]

    url1 = "https://drive.google.com/drive/home"
    # url2 = "https://www.allrecipes.com/recipe/21151/simple-whole-roast-chicken/"

    response = client.models.generate_content(
        model=model_id,
        contents=f"is this login page or page needing login? if yes return login button id or a link to login page{url1}",
        config=GenerateContentConfig(
            tools=tools,
        )
    )

    for each in response.candidates[0].content.parts:
        print(each.text)

    # For verification, you can inspect the metadata to see which URLs the model retrieved
    print(response.candidates[0].url_context_metadata)

if __name__ == "__main__":
    test_chat_with()
    # chat_with_gemini_with_link()