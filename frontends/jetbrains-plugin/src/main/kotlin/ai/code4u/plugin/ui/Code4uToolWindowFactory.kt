package ai.code4u.plugin.ui

import ai.code4u.plugin.client.ChatContext
import ai.code4u.plugin.client.ChatRequest
import ai.code4u.plugin.client.Code4uClient
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.content.ContentFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.swing.Swing
import java.awt.BorderLayout
import java.awt.Color
import java.awt.event.KeyAdapter
import java.awt.event.KeyEvent
import java.util.UUID
import javax.swing.*
import javax.swing.border.EmptyBorder

class Code4uToolWindowFactory : ToolWindowFactory {
    
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val chatPanel = Code4uChatPanel(project)
        val content = ContentFactory.getInstance().createContent(chatPanel, "Agent", false)
        toolWindow.contentManager.addContent(content)
    }
}

class Code4uChatPanel(private val project: Project) : JPanel(BorderLayout()) {
    
    private val client = Code4uClient()
    private val messagesPanel = JPanel()
    private val inputField = JTextArea(3, 40)
    private var conversationId: String? = null
    
    init {
        background = Color(30, 30, 30)
        
        // Messages area
        messagesPanel.layout = BoxLayout(messagesPanel, BoxLayout.Y_AXIS)
        messagesPanel.background = Color(30, 30, 30)
        
        val scrollPane = JBScrollPane(messagesPanel).apply {
            border = null
            verticalScrollBarPolicy = ScrollPaneConstants.VERTICAL_SCROLLBAR_AS_NEEDED
        }
        
        // Input area
        inputField.apply {
            background = Color(45, 45, 45)
            foreground = Color.WHITE
            caretColor = Color.WHITE
            border = EmptyBorder(10, 10, 10, 10)
            lineWrap = true
            wrapStyleWord = true
        }
        
        inputField.addKeyListener(object : KeyAdapter() {
            override fun keyPressed(e: KeyEvent) {
                if (e.keyCode == KeyEvent.VK_ENTER && !e.isShiftDown) {
                    e.consume()
                    sendMessage()
                }
            }
        })
        
        val sendButton = JButton("Send").apply {
            background = Color(0, 150, 136)
            foreground = Color.WHITE
            addActionListener { sendMessage() }
        }
        
        val inputPanel = JPanel(BorderLayout()).apply {
            background = Color(40, 40, 40)
            border = EmptyBorder(10, 10, 10, 10)
            add(JBScrollPane(inputField), BorderLayout.CENTER)
            add(sendButton, BorderLayout.EAST)
        }
        
        // Header
        val headerPanel = JPanel(BorderLayout()).apply {
            background = Color(25, 25, 25)
            border = EmptyBorder(10, 15, 10, 15)
            
            val titleLabel = JLabel("code4u.ai Agent").apply {
                foreground = Color(0, 200, 150)
                font = font.deriveFont(14f)
            }
            
            val newChatButton = JButton("New Chat").apply {
                addActionListener { 
                    conversationId = null
                    messagesPanel.removeAll()
                    messagesPanel.revalidate()
                    messagesPanel.repaint()
                }
            }
            
            add(titleLabel, BorderLayout.WEST)
            add(newChatButton, BorderLayout.EAST)
        }
        
        // Welcome message
        addMessage("assistant", "👋 Hello! I'm your code4u.ai agent. I can help you:\n\n• Refactor code safely\n• Explain complex logic\n• Generate new code\n• Analyze impact of changes\n\nHow can I assist you today?")
        
        add(headerPanel, BorderLayout.NORTH)
        add(scrollPane, BorderLayout.CENTER)
        add(inputPanel, BorderLayout.SOUTH)
    }
    
    private fun sendMessage() {
        val message = inputField.text.trim()
        if (message.isBlank()) return
        
        inputField.text = ""
        addMessage("user", message)
        
        if (conversationId == null) {
            conversationId = UUID.randomUUID().toString()
        }
        
        val request = ChatRequest(
            message = message,
            conversation_id = conversationId,
            context = ChatContext(
                file_path = null, // Could get current file
                selection = null,
                language = null
            )
        )
        
        val responseBuilder = StringBuilder()
        val responseLabel = addMessage("assistant", "...")
        
        CoroutineScope(Dispatchers.IO).launch {
            client.chat(
                request = request,
                onMessage = { chatMessage ->
                    if (chatMessage.role == "assistant") {
                        responseBuilder.append(chatMessage.content)
                        launch(Dispatchers.Swing) {
                            responseLabel.text = formatMessage(responseBuilder.toString())
                        }
                    }
                },
                onComplete = {},
                onError = { error ->
                    launch(Dispatchers.Swing) {
                        responseLabel.text = "<html><font color='red'>Error: $error</font></html>"
                    }
                }
            )
        }
    }
    
    private fun addMessage(role: String, content: String): JLabel {
        val isUser = role == "user"
        
        val messagePanel = JPanel(BorderLayout()).apply {
            background = if (isUser) Color(45, 45, 45) else Color(35, 35, 35)
            border = EmptyBorder(10, 15, 10, 15)
            maximumSize = java.awt.Dimension(Int.MAX_VALUE, Int.MAX_VALUE)
        }
        
        val roleLabel = JLabel(if (isUser) "You" else "code4u.ai").apply {
            foreground = if (isUser) Color(100, 180, 255) else Color(0, 200, 150)
            font = font.deriveFont(java.awt.Font.BOLD, 12f)
        }
        
        val contentLabel = JLabel(formatMessage(content)).apply {
            foreground = Color.WHITE
            border = EmptyBorder(5, 0, 0, 0)
        }
        
        val innerPanel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            background = messagePanel.background
            add(roleLabel)
            add(contentLabel)
        }
        
        messagePanel.add(innerPanel, BorderLayout.CENTER)
        messagesPanel.add(messagePanel)
        messagesPanel.add(Box.createVerticalStrut(5))
        messagesPanel.revalidate()
        messagesPanel.repaint()
        
        // Scroll to bottom
        SwingUtilities.invokeLater {
            val scrollPane = SwingUtilities.getAncestorOfClass(JScrollPane::class.java, messagesPanel) as? JScrollPane
            scrollPane?.verticalScrollBar?.value = scrollPane?.verticalScrollBar?.maximum ?: 0
        }
        
        return contentLabel
    }
    
    private fun formatMessage(content: String): String {
        return "<html><body style='width: 300px'>${content.replace("\n", "<br>")}</body></html>"
    }
}

