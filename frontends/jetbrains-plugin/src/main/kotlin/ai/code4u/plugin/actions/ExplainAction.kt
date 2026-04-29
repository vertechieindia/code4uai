package ai.code4u.plugin.actions

import ai.code4u.plugin.client.ChatContext
import ai.code4u.plugin.client.ChatRequest
import ai.code4u.plugin.client.Code4uClient
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.ui.popup.JBPopupFactory
import com.intellij.openapi.ui.popup.util.PopupUtil
import com.intellij.ui.components.JBScrollPane
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.swing.Swing
import java.awt.Dimension
import javax.swing.JTextArea

class ExplainAction : AnAction() {
    
    private val client = Code4uClient()
    
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE)
        
        val selection = editor.selectionModel.selectedText
        if (selection.isNullOrBlank()) {
            return
        }
        
        val textArea = JTextArea().apply {
            isEditable = false
            lineWrap = true
            wrapStyleWord = true
            text = "Analyzing code..."
        }
        
        val scrollPane = JBScrollPane(textArea).apply {
            preferredSize = Dimension(500, 300)
        }
        
        val popup = JBPopupFactory.getInstance()
            .createComponentPopupBuilder(scrollPane, null)
            .setTitle("code4u.ai - Code Explanation")
            .setMovable(true)
            .setResizable(true)
            .createPopup()
        
        popup.showInBestPositionFor(editor)
        
        val request = ChatRequest(
            message = "Explain this code:\n\n```\n$selection\n```",
            context = ChatContext(
                file_path = file?.path,
                selection = selection,
                language = file?.extension
            )
        )
        
        CoroutineScope(Dispatchers.IO).launch {
            val explanation = StringBuilder()
            
            client.chat(
                request = request,
                onMessage = { message ->
                    if (message.role == "assistant") {
                        explanation.append(message.content)
                        launch(Dispatchers.Swing) {
                            textArea.text = explanation.toString()
                        }
                    }
                },
                onComplete = {},
                onError = { error ->
                    launch(Dispatchers.Swing) {
                        textArea.text = "Error: $error"
                    }
                }
            )
        }
    }
    
    override fun update(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR)
        val hasSelection = editor?.selectionModel?.hasSelection() == true
        e.presentation.isEnabledAndVisible = hasSelection
    }
}

