package ai.code4u.plugin.actions

import ai.code4u.plugin.settings.Code4uSettings
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.ui.Messages

class ToggleAutocompleteAction : AnAction() {
    
    private val settings = Code4uSettings.instance
    
    override fun actionPerformed(e: AnActionEvent) {
        settings.autocompleteEnabled = !settings.autocompleteEnabled
        settings.inlineCompletionEnabled = !settings.inlineCompletionEnabled
        
        val status = if (settings.autocompleteEnabled) "enabled" else "disabled"
        Messages.showInfoMessage(
            e.project,
            "code4u.ai autocomplete is now $status",
            "code4u.ai"
        )
    }
    
    override fun update(e: AnActionEvent) {
        val status = if (settings.autocompleteEnabled) "Disable" else "Enable"
        e.presentation.text = "$status code4u Autocomplete"
    }
}

