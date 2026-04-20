"""视频处理管道（Pipeline 类）测试。"""

import pytest
from app.processing.pipeline import Pipeline, Filter


class SimpleFilter(Filter):
    """简单的测试过滤器，向数据中添加一个键。"""

    def __init__(self, name: str, key: str, value):
        self._name = name
        self._key = key
        self._value = value

    def process(self, data, context):
        data[self._key] = self._value
        context[f"{self._key}_processed"] = True
        return data

    def get_name(self):
        return self._name


class ErrorFilter(Filter):
    """总是抛出错误的过滤器。"""

    def process(self, data, context):
        raise RuntimeError("测试过滤器错误")

    def get_name(self):
        return "ErrorFilter"


class TestPipeline:
    """测试 Pipeline 类。"""

    def test_empty_pipeline(self):
        pipeline = Pipeline(name="test")
        result = pipeline.execute({"input": "data"})
        assert result == {"input": "data"}

    def test_single_filter(self):
        pipeline = Pipeline(name="test")
        pipeline.add_filter(SimpleFilter("f1", "step1", "done"))
        result = pipeline.execute({"input": "data"})
        assert result["step1"] == "done"

    def test_multiple_filters(self):
        pipeline = Pipeline(name="test")
        pipeline.add_filter(SimpleFilter("f1", "step1", "a"))
        pipeline.add_filter(SimpleFilter("f2", "step2", "b"))
        pipeline.add_filter(SimpleFilter("f3", "step3", "c"))
        result = pipeline.execute({"input": "data"})
        assert result["step1"] == "a"
        assert result["step2"] == "b"
        assert result["step3"] == "c"

    def test_context_shared_between_filters(self):
        pipeline = Pipeline(name="test")
        pipeline.add_filter(SimpleFilter("f1", "step1", "a"))
        pipeline.add_filter(SimpleFilter("f2", "step2", "b"))
        context = {}
        pipeline.execute({"input": "data"}, context)
        assert context["step1_processed"] is True
        assert context["step2_processed"] is True

    def test_filter_error_propagates(self):
        pipeline = Pipeline(name="test")
        pipeline.add_filter(SimpleFilter("f1", "step1", "a"))
        pipeline.add_filter(ErrorFilter())
        with pytest.raises(RuntimeError, match="测试过滤器错误"):
            pipeline.execute({"input": "data"})

    def test_get_filter_names(self):
        pipeline = Pipeline(name="test")
        pipeline.add_filter(SimpleFilter("解码器", "d", 1))
        pipeline.add_filter(SimpleFilter("处理器", "p", 2))
        pipeline.add_filter(SimpleFilter("编码器", "e", 3))
        names = pipeline.get_filter_names()
        assert names == ["解码器", "处理器", "编码器"]

    def test_clear_filters(self):
        pipeline = Pipeline(name="test")
        pipeline.add_filter(SimpleFilter("f1", "step1", "a"))
        pipeline.clear_filters()
        names = pipeline.get_filter_names()
        assert names == []

    def test_chaining(self):
        pipeline = Pipeline(name="test")
        result = pipeline.add_filter(SimpleFilter("f1", "a", 1))
        assert result is pipeline  # 应返回 self

    def test_default_context(self):
        pipeline = Pipeline(name="test")
        pipeline.add_filter(SimpleFilter("f1", "step1", "a"))
        result = pipeline.execute({"input": "data"})
        # 未提供 context 时应自动创建
        assert result["step1"] == "a"
