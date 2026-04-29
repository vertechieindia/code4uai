package ai.code4u.plugin.ui

import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.DialogWrapper
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.components.JBTextArea
import java.awt.BorderLayout
import java.awt.Dimension
import javax.swing.*
import javax.swing.border.EmptyBorder

class RefactorDialog(
    project: Project,
    private val selectedCode: String?
) : DialogWrapper(project) {
    
    private val intentField = JBTextArea(4, 50)
    
    init {
        title = "code4u.ai - Refactor"
        init()
    }
    
    override fun createCenterPanel(): JComponent {
        val panel = JPanel(BorderLayout(10, 10)).apply {
            border = EmptyBorder(10, 10, 10, 10)
        }
        
        // Instructions
        val instructionLabel = JLabel("<html><b>Describe your refactoring intent:</b></html>")
        
        // Intent input
        intentField.apply {
            lineWrap = true
            wrapStyleWord = true
            text = if (selectedCode != null) {
                "Refactor the selected code: "
            } else {
                ""
            }
        }
        
        val intentScroll = JBScrollPane(intentField).apply {
            preferredSize = Dimension(400, 100)
        }
        
        // Selected code preview
        val previewPanel = if (selectedCode != null && selectedCode.length < 500) {
            JPanel(BorderLayout()).apply {
                border = BorderFactory.createTitledBorder("Selected Code")
                add(JBScrollPane(JTextArea(selectedCode).apply {
                    isEditable = false
                    lineWrap = true
                    rows = 5
                }), BorderLayout.CENTER)
            }
        } else null
        
        // Examples
        val examplesPanel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            border = BorderFactory.createTitledBorder("Examples")
            
            listOf(
                "Rename variable 'x' to 'userCount'",
                "Extract this logic into a separate function",
                "Add error handling with try-catch",
                "Convert to async/await pattern",
                "Add logging statements"
            ).forEach { example ->
                add(JButton(example).apply {
                    addActionListener { intentField.text = example }
                    alignmentX = LEFT_ALIGNMENT
                    maximumSize = Dimension(Int.MAX_VALUE, preferredSize.height)
                })
            }
        }
        
        val contentPanel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            add(instructionLabel)
            add(Box.createVerticalStrut(10))
            add(intentScroll)
            previewPanel?.let {
                add(Box.createVerticalStrut(10))
                add(it)
            }
            add(Box.createVerticalStrut(10))
            add(examplesPanel)
        }
        
        panel.add(contentPanel, BorderLayout.CENTER)
        
        return panel
    }
    
    fun getIntent(): String = intentField.text.trim()
}

