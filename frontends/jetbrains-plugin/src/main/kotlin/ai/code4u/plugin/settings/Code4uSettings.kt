package ai.code4u.plugin.settings

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage

@Service
@State(
    name = "Code4uSettings",
    storages = [Storage("code4u.xml")]
)
class Code4uSettings : PersistentStateComponent<Code4uSettings.State> {
    
    data class State(
        var serverUrl: String = "http://localhost:8002",
        var apiKey: String = "",
        var tenantId: String = "default",
        var autocompleteEnabled: Boolean = true,
        var inlineCompletionEnabled: Boolean = true,
        var autoTriggerDelay: Int = 300, // ms
        var maxCompletions: Int = 5,
        var showDocumentation: Boolean = true,
        var telemetryEnabled: Boolean = true,
        var debugMode: Boolean = false
    )
    
    private var state = State()
    
    override fun getState(): State = state
    
    override fun loadState(state: State) {
        this.state = state
    }
    
    var serverUrl: String
        get() = state.serverUrl
        set(value) { state.serverUrl = value }
    
    var apiKey: String
        get() = state.apiKey
        set(value) { state.apiKey = value }
    
    var tenantId: String
        get() = state.tenantId
        set(value) { state.tenantId = value }
    
    var autocompleteEnabled: Boolean
        get() = state.autocompleteEnabled
        set(value) { state.autocompleteEnabled = value }
    
    var inlineCompletionEnabled: Boolean
        get() = state.inlineCompletionEnabled
        set(value) { state.inlineCompletionEnabled = value }
    
    var autoTriggerDelay: Int
        get() = state.autoTriggerDelay
        set(value) { state.autoTriggerDelay = value }
    
    var maxCompletions: Int
        get() = state.maxCompletions
        set(value) { state.maxCompletions = value }
    
    var showDocumentation: Boolean
        get() = state.showDocumentation
        set(value) { state.showDocumentation = value }
    
    var telemetryEnabled: Boolean
        get() = state.telemetryEnabled
        set(value) { state.telemetryEnabled = value }
    
    var debugMode: Boolean
        get() = state.debugMode
        set(value) { state.debugMode = value }
    
    companion object {
        val instance: Code4uSettings
            get() = ApplicationManager.getApplication().getService(Code4uSettings::class.java)
    }
}

