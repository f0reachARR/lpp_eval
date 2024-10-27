from jinja2 import Environment


def render(template_name: str, parameters: dict):
    with open(f"./templates/{template_name}") as f:
        text = f.read()
    env = Environment()
    template = env.from_string(text)
    text = template.render(parameters)
    return text
