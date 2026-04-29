package ai.code4u.plugin.actions

import ai.code4u.plugin.client.Code4uClient
import ai.code4u.plugin.client.ImpactRequest
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.ui.popup.JBPopupFactory
import com.intellij.ui.components.JBScrollPane
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.swing.Swing
import java.awt.Dimension
import javax.swing.JTextArea

class AnalyzeImpactAction : AnAction() {
    
    private val client = Code4uClient()
    
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE) ?: return
        
        val selection = editor.selectionModel.selectedText
        
        val textArea = JTextArea().apply {
            isEditable = false
            lineWrap = true
            wrapStyleWord = true
            text = "Analyzing impact..."
        }
        
        val scrollPane = JBScrollPane(textArea).apply {
            preferredSize = Dimension(400, 300)
        }
        
        val popup = JBPopupFactory.getInstance()
            .createComponentPopupBuilder(scrollPane, null)
            .setTitle("code4u.ai - Impact Analysis")
            .setMovable(true)
            .setResizable(true)
            .createPopup()
        
        popup.showInBestPositionFor(editor)
        
        val request = ImpactRequest(
            file_path = file.path,
            symbol = selection
        )
        
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = client.analyzeImpact(request)
                launch(Dispatchers.Swing) {
                    if (response != null) {
                        val sb = StringBuilder()
                        sb.appendLine("📊 Impact Analysis")
                        sb.appendLine("═".repeat(40))
                        sb.appendLine()
                        sb.appendLine("🎯 Risk Level: ${response.risk_level}")
                        sb.appendLine("⚠️ Breaking Changes: ${if (response.breaking_changes) "Yes" else "No"}")
                        sb.appendLine()
                        sb.appendLine("📁 Impacted Files (${response.impacted_files.size}):")
                        response.impacted_files.forEach { 
                            sb.appendLine("  • $it")
                        }
                        sb.appendLine()
                        sb.appendLine("🔗 Impacted Symbols (${response.impacted_symbols.size}):")
                        response.impacted_symbols.forEach {
                            sb.appendLine("  • $it")
                        }
                        textArea.text = sb.toString()
                    } else {
                        textArea.text = "No impact data available"
                    }
                }
            } catch (ex: Exception) {
                launch(Dispatchers.Swing) {
                    textArea.text = "Error: ${ex.message}"
                }
            }
        }
    }
    
    override fun update(e: AnActionEvent) {
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE)
        e.presentation.isEnabledAndVisible = file != null
    }
}

