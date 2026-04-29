package ai.code4u.plugin.settings

import ai.code4u.plugin.client.Code4uClient
import com.intellij.openapi.options.Configurable
import com.intellij.openapi.ui.DialogPanel
import com.intellij.ui.components.JBCheckBox
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBPasswordField
import com.intellij.ui.components.JBTextField
import com.intellij.ui.dsl.builder.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.swing.Swing
import javax.swing.JButton
import javax.swing.JComponent

class Code4uConfigurable : Configurable {
    private val settings = Code4uSettings.instance
    private var panel: DialogPanel? = null
    
    private var serverUrlField = JBTextField()
    private var apiKeyField = JBPasswordField()
    private var tenantIdField = JBTextField()
    private var autocompleteCheckbox = JBCheckBox()
    private var inlineCompletionCheckbox = JBCheckBox()
    private var delayField = JBTextField()
    private var maxCompletionsField = JBTextField()
    private var showDocsCheckbox = JBCheckBox()
    private var telemetryCheckbox = JBCheckBox()
    private var debugCheckbox = JBCheckBox()
    private var connectionStatus = JBLabel()
    
    override fun getDisplayName(): String = "code4u.ai"
    
    override fun createComponent(): JComponent {
        panel = panel {
            group("Connection") {
                row("Server URL:") {
                    cell(serverUrlField)
                        .columns(COLUMNS_LARGE)
                        .comment("code4u.ai backend URL")
                }
                row("API Key:") {
                    cell(apiKeyField)
                        .columns(COLUMNS_LARGE)
                        .comment("Your code4u.ai API key")
                }
                row("Tenant ID:") {
                    cell(tenantIdField)
                        .columns(COLUMNS_MEDIUM)
                        .comment("Your organization's tenant ID")
                }
                row {
                    val testButton = JButton("Test Connection")
                    testButton.addActionListener { testConnection() }
                    cell(testButton)
                    cell(connectionStatus)
                }
            }
            
            group("Autocomplete") {
                row {
                    cell(autocompleteCheckbox)
                        .label("Enable Autocomplete")
                        .comment("Show code completions as you type")
                }
                row {
                    cell(inlineCompletionCheckbox)
                        .label("Enable Inline Completion (Tab)")
                        .comment("Show multi-line suggestions with Tab to accept")
                }
                row("Trigger Delay (ms):") {
                    cell(delayField)
                        .columns(COLUMNS_SHORT)
                        .comment("Delay before showing completions")
                }
                row("Max Completions:") {
                    cell(maxCompletionsField)
                        .columns(COLUMNS_SHORT)
                        .comment("Maximum number of suggestions to show")
                }
                row {
                    cell(showDocsCheckbox)
                        .label("Show Documentation")
                        .comment("Show documentation popup for completions")
                }
            }
            
            group("Privacy & Debug") {
                row {
                    cell(telemetryCheckbox)
                        .label("Enable Telemetry")
                        .comment("Help improve code4u.ai by sending anonymous usage data")
                }
                row {
                    cell(debugCheckbox)
                        .label("Debug Mode")
                        .comment("Enable detailed logging for troubleshooting")
                }
            }
        }
        
        reset()
        return panel!!
    }
    
    private fun testConnection() {
        connectionStatus.text = "Testing..."
        CoroutineScope(Dispatchers.IO).launch {
            val client = Code4uClient()
            val success = client.testConnection()
            launch(Dispatchers.Swing) {
                connectionStatus.text = if (success) {
                    "<html><font color='green'>✓ Connected</font></html>"
                } else {
                    "<html><font color='red'>✗ Connection failed</font></html>"
                }
            }
        }
    }
    
    override fun isModified(): Boolean {
        return serverUrlField.text != settings.serverUrl ||
               String(apiKeyField.password) != settings.apiKey ||
               tenantIdField.text != settings.tenantId ||
               autocompleteCheckbox.isSelected != settings.autocompleteEnabled ||
               inlineCompletionCheckbox.isSelected != settings.inlineCompletionEnabled ||
               delayField.text.toIntOrNull() != settings.autoTriggerDelay ||
               maxCompletionsField.text.toIntOrNull() != settings.maxCompletions ||
               showDocsCheckbox.isSelected != settings.showDocumentation ||
               telemetryCheckbox.isSelected != settings.telemetryEnabled ||
               debugCheckbox.isSelected != settings.debugMode
    }
    
    override fun apply() {
        settings.serverUrl = serverUrlField.text
        settings.apiKey = String(apiKeyField.password)
        settings.tenantId = tenantIdField.text
        settings.autocompleteEnabled = autocompleteCheckbox.isSelected
        settings.inlineCompletionEnabled = inlineCompletionCheckbox.isSelected
        settings.autoTriggerDelay = delayField.text.toIntOrNull() ?: 300
        settings.maxCompletions = maxCompletionsField.text.toIntOrNull() ?: 5
        settings.showDocumentation = showDocsCheckbox.isSelected
        settings.telemetryEnabled = telemetryCheckbox.isSelected
        settings.debugMode = debugCheckbox.isSelected
    }
    
    override fun reset() {
        serverUrlField.text = settings.serverUrl
        apiKeyField.text = settings.apiKey
        tenantIdField.text = settings.tenantId
        autocompleteCheckbox.isSelected = settings.autocompleteEnabled
        inlineCompletionCheckbox.isSelected = settings.inlineCompletionEnabled
        delayField.text = settings.autoTriggerDelay.toString()
        maxCompletionsField.text = settings.maxCompletions.toString()
        showDocsCheckbox.isSelected = settings.showDocumentation
        telemetryCheckbox.isSelected = settings.telemetryEnabled
        debugCheckbox.isSelected = settings.debugMode
    }
}

