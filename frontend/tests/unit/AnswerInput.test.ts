import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AnswerInput from "../../src/components/AnswerInput.vue";

describe("four-type answer input", () => {
  const options = ["A", "B", "C", "D"].map((id) => ({ id, text: `选项${id}` }));
  it("selects an option ID instead of its display text", async () => {
    const wrapper = mount(AnswerInput, {
      props: { kind: "single", options, modelValue: null },
    });
    await wrapper.get('input[value="B"]').setValue(true);
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual(["B"]);
  });
  it("emits a boolean false rather than the string false", async () => {
    const wrapper = mount(AnswerInput, {
      props: { kind: "boolean", options: [], modelValue: null },
    });
    await wrapper.get('input[value="false"]').setValue(true);
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([false]);
  });
  it("retains an existing multiple selection while adding another", async () => {
    const wrapper = mount(AnswerInput, {
      props: { kind: "multiple", options, modelValue: ["A"] },
    });
    await wrapper.get('input[value="B"]').setValue(true);
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([["A", "B"]]);
  });
  it("preserves case and raw fill input for auditable grading", async () => {
    const wrapper = mount(AnswerInput, {
      props: { kind: "fill", options: [], modelValue: "" },
    });
    await wrapper.get('input[type="text"]').setValue("HTTP");
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual(["HTTP"]);
  });
});
