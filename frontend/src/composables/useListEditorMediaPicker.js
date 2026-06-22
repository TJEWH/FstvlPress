import { ref } from "vue";

export function useListEditorMediaPicker() {
  const showMediaPicker = ref(false);
  const mediaPickerTargetIndex = ref(-1);
  const mediaPickerDirectUpdate = ref(false);

  function openMediaPicker(index, options = {}) {
    mediaPickerTargetIndex.value = Number.isInteger(index) ? index : -1;
    mediaPickerDirectUpdate.value = Boolean(options?.direct);
    showMediaPicker.value = true;
  }

  function closeMediaPicker() {
    showMediaPicker.value = false;
    mediaPickerTargetIndex.value = -1;
    mediaPickerDirectUpdate.value = false;
  }

  function consumeMediaPickerSelectionContext() {
    return {
      index: mediaPickerTargetIndex.value,
      direct: mediaPickerDirectUpdate.value,
    };
  }

  return {
    showMediaPicker,
    mediaPickerTargetIndex,
    openMediaPicker,
    closeMediaPicker,
    consumeMediaPickerSelectionContext,
  };
}
