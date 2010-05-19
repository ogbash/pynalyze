
class Block(object):
    """
    Abstract base class for blocks in Control/Data Flow analysis.

    This class is a common base class for basic blocks and composite
    types of blocks (If, Do, Case, and other blocks). It defines
    interface of methods and common implementation which can be
    redefined in subclasses.

    @ivar model: control flow model that this block belongs to
    @type model: L{ControlFlowModel}
    """

    def __init__(self, model, parentBlock, subBlocks = []):
        self.model = model # control flow model
        self.parentBlock = parentBlock
        self.subBlocks = list(subBlocks)
        self.firstBlock = self.subBlocks and self.subBlocks[0] or None
        self.endBlock = None

        self._nextBasicBlocks = None
        self._previousBasicBlocks = None

        self.astObjects = []

    def getFirstBasicBlock(self):
        """The first basic block that is run when entering this block.
        @rtype: L{BasicBlock}
        """
        if self.firstBlock==None:
            return None

        if isinstance(self.firstBlock, BasicBlock):
            return self.firstBlock
        else:
            return self.firstBlock.getFirstBasicBlock()

    def getEndBlock(self):
        """The following block after exiting this block.
        @rtype: L{Block}
        """
        if self.endBlock==None and self.parentBlock!=None:
            return self.parentBlock.getEndBlock()
        return self.endBlock

    def getNextBasicBlocks(self):
        """Basic blocks that may be executed after exiting this block.
        @return: list of basic blocks
        @rtype: list of L{BasicBlock}s
        """
        if self._nextBasicBlocks==None:
            nextBlock = self.getEndBlock().getFirstBasicBlock()
            if nextBlock is not None:
                self._nextBasicBlocks = [nextBlock]
            else:
                self._nextBasicBlocks = []
        return self._nextBasicBlocks

    def getPreviousBasicBlocks(self):
        if self._previousBasicBlocks == None:
            self.model._calculatePreviousBasicBlocks()
        return self._previousBasicBlocks

    def __str__(self):
        return "<%s(%s)>" % (self.__class__.__name__,
                             (self.astObjects and self.astObjects[-1] or ''))

    def addSubBlocks(self, blocks):
        self.subBlocks.extend(blocks)
        if self.subBlocks:
            self.firstBlock = self.subBlocks[0]

    def itertree(self, callback):
        for b in self.subBlocks:
            b.itertree(callback)
        callback(self)

    def hasInside(self, block):
        if block==self:
            return True
        if block.parentBlock!=None:
            return self.hasInside(block.parentBlock)
        return False

class BasicBlock(Block):

    def __init__(self, model, parentBlock, executions):
        Block.__init__(self, model, parentBlock)
        self.executions = executions

        self.astObjects.extend(executions)

    def getFirstBasicBlock(self):
        return self


class StartBlock(BasicBlock):
    def __init__(self, model, parentBlock):
        BasicBlock.__init__(self, model, parentBlock, [])

class EndBlock(BasicBlock):
    def __init__(self, model, parentBlock):
        BasicBlock.__init__(self, model, parentBlock, [])

    def getNextBasicBlocks(self):
        return []

class ConditionBlock(BasicBlock):

    def __init__(self, model, parentBlock, executions):
        BasicBlock.__init__(self, model, parentBlock, executions)
        self.branchBlocks = []

    def getNextBasicBlocks(self):
        if self._nextBasicBlocks==None:
            blocks = []
            for branchBlock in self.branchBlocks:
                nextBlock = branchBlock.getFirstBasicBlock()
                if nextBlock is not None:
                    blocks.append(nextBlock)
            nextBlocks = super(ConditionBlock,self).getNextBasicBlocks()
            blocks.extend(nextBlocks)
            self._nextBasicBlocks = blocks
        return self._nextBasicBlocks

class ControlFlowModel(object):

    "Model allows to navigate through AST tree of a subroutine or a program."

    def __init__(self, astObj, statements):
        self.code = astObj
        self.block = Block(self, None)

        self._startBlock = StartBlock(self, self.block)
        self._endBlock = EndBlock(self, self.block)
        self._codeBlock = Block(self, self.block)
        blocks = self.generateBlocks(self._codeBlock, statements)
        self._codeBlock.subBlocks = blocks
        
        self.block.subBlocks = [self._startBlock,self._codeBlock,self._endBlock]
        self.block.firstBlock = self._startBlock
        self._codeBlock.firstBlock = blocks[0]
        self._startBlock.endBlock = self._codeBlock
        self._codeBlock.endBlock = self._endBlock

        self._connections = None

        self._resolveJumpStatements()
        self._allBasicBlocks = None

    def generateBlocks(self, parentBlock, statements):
        statments = list(statements)
        blocks = []
        
        simpleStatements = []
        while len(statements)>0:
            stmt = statements[0]
            if stmt.__class__ in self.CLASS_MAP.keys():
                # statement with subblocks
                BlockClass = self.CLASS_MAP[stmt.__class__]
                if simpleStatements:
                    # create basic block from up-to-now simple statements
                    blocks.append(BasicBlock(self, parentBlock, simpleStatements))
                    simpleStatements = []
    
                subBlock = BlockClass(self, parentBlock, stmt)
                blocks.append(subBlock)
                del statements[0]

            else:
                # simple statement
                simpleStatements.append(stmt)
                del statements[0]
                
                # TODO break?? should finish simple statements and start new without breaking!!
                if isinstance(stmt, self.JUMP_STATEMENT_CLASSES):
                    break

        if simpleStatements:
            blocks.append(BasicBlock(self, parentBlock, simpleStatements))
            simpleStatements = []

        for i in xrange(len(blocks)-1):
            blocks[i].endBlock = blocks[i+1]

        return blocks

    def _resolveJumpStatements(self):
        pass

    def _calculatePreviousBasicBlocks(self):
        allBlocks = self.getAllBasicBlocks()
        for block in allBlocks:
            block._previousBasicBlocks = []

        for block in allBlocks:
            for nextBlock in block.getNextBasicBlocks():
                nextBlock._previousBasicBlocks.append(block)

    def getAllBasicBlocks(self):
        if self._allBasicBlocks==None:            
            blocks = set()

            def collect(block):
                if isinstance(block, BasicBlock):
                    blocks.add(block)

            self.block.itertree(collect)
            self._allBasicBlocks = blocks

        return self._allBasicBlocks

    def getConnections(self):
        if self._connections==None:
            connections = set()
            processed = set()
            blocks = set()
            blocks.add(self.block.getFirstBasicBlock())
            while blocks:
                block = blocks.pop()
                processed.add(block)
                nextBlocks = block.getNextBasicBlocks()
                for nextBlock in nextBlocks:
                    connections.add((block, nextBlock))
                    if nextBlock!=None and not nextBlock in processed:
                        blocks.add(nextBlock)
            self._connections = connections
        return self._connections

    def classifyConnectionsBy(self, connections, blocks):
        """Takes list of tuples and divides them into classes, where
        each class is some connection for I{blocks} and its elements
        are all connections of the subBlocks of I{blocks}.
        """
        blockSet = set(blocks)

        def find(block):
            while not block in blockSet and block!=None:
                block = block.parentBlock
            return block

        clConnections = {}
        for blockFrom, blockTo in connections:
            clBlockFrom = find(blockFrom)
            clBlockTo = find(blockTo)
            if not clConnections.has_key((clBlockFrom,clBlockTo)):
                clConnections[(clBlockFrom,clBlockTo)] = []
            clConnections[(clBlockFrom,clBlockTo)].append((blockFrom,blockTo))

        return clConnections
