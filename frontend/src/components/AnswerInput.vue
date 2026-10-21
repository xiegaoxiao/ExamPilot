<script setup lang="ts">
import type { Answer, Kind } from "../lib/types";
const props = defineProps<{
  kind: Kind;
  options: { id: string; text: string }[];
  modelValue: Answer;
  disabled?: boolean;
}>();
const emit = defineEmits<{ "update:modelValue": [value: Answer] }>();
function multiple(id: string, checked: boolean) {
  const current = Array.isArray(props.modelValue) ? props.modelValue : [];
  emit(
    "update:modelValue",
    checked ? [...current, id] : current.filter((x) => x !== id),
  );
}
</script>
<template>
  <div class="answer-input">
    <template v-if="kind === 'single' || kind === 'multiple'"
      ><label
        v-for="option in options"
        :key="option.id"
        class="answer-option"
        :class="{
          selected:
            kind === 'multiple'
              ? Array.isArray(modelValue) && modelValue.includes(option.id)
              : modelValue === option.id,
        }"
        ><input
          :type="kind === 'multiple' ? 'checkbox' : 'radio'"
          :value="option.id"
          :disabled="disabled"
          :checked="
            kind === 'multiple'
              ? Array.isArray(modelValue) && modelValue.includes(option.id)
              : modelValue === option.id
          "
          @change="
            kind === 'multiple'
              ? multiple(option.id, ($event.target as HTMLInputElement).checked)
              : emit('update:modelValue', option.id)
          "
        /><span class="option-letter">{{ option.id }}</span
        ><span>{{ option.text }}</span></label
      ></template
    >
    <template v-else-if="kind === 'boolean'"
      ><label
        v-for="value in [true, false]"
        :key="String(value)"
        class="answer-option"
        :class="{ selected: modelValue === value }"
        ><input
          type="radio"
          :value="String(value)"
          :disabled="disabled"
          :checked="modelValue === value"
          @change="emit('update:modelValue', value)"
        /><span class="option-letter">{{ value ? "✓" : "✕" }}</span
        ><span>{{ value ? "正确" : "错误" }}</span></label
      ></template
    >
    <input
      v-else
      type="text"
      class="text-input fill-input"
      placeholder="请输入你的答案"
      :value="typeof modelValue === 'string' ? modelValue : ''"
      :disabled="disabled"
      maxlength="200"
      aria-label="填空答案"
      @input="
        emit('update:modelValue', ($event.target as HTMLInputElement).value)
      "
    />
  </div>
</template>
