from setuptools import setup, find_packages

setup(
    name="voice_access_control",   # 项目包名（随便起，但保持英文）
    version="0.1",
    packages=find_packages(),      # 自动找到所有带 __init__.py 的包
    include_package_data=True,
)
