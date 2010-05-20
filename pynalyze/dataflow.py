import controlflow as cf

class Dict(object):
    def __init__(self, d=None):
        if d!=None:
            self._values = self._copyDict(d._values)
        else:
            self._values = {}            

    def _copyDict(self, d):
        v = {}
        for key in d.keys():
            if isinstance(d[key], dict):
                v[key] = self._copyDict(d[key])
            else:
                v[key] = d[key]
        return v

    def __getitem__(self, key):
        d = self._values
        for name in key:
            if not d.has_key(name):
                return None
            d = d[name]

        return d.get(None, None)

    def __setitem__(self, key, value):
        d = self._values
        for name in key:
            if not d.has_key(name):
                d[name]={}
            d = d[name]
        d[None] = value

    def add(self, key, loc):
        d = self._values
        for name in key:
            if not d.has_key(name):
                d[name]={}
            d = d[name]
        if not d.has_key(None):
            d[None] = set()
        d[None].add(loc)

    def remove(self, key):
        d = self._values
        for name in key:
            if not d.has_key(name):
                return False
            p = d
            d = d[name]
        del p[name]

    def _update(self, toDict, fromDict):
        for name in fromDict.keys():
            if name is None:
                # value
                if not toDict.has_key(name):
                    toDict[name] = set()
                toDict[name].update(fromDict[name])
            else:
                # subcomponent with name
                if not toDict.has_key(name):
                    toDict[name] = dict()
                self._update(toDict[name], fromDict[name])

    def update(self, fromDict):
        self._update(self._values, fromDict._values)

    def __eq__(self, d):
        if d is None:
            return False
        return self._values==d._values

    def __ne__(self, d):
        if d is None:
            return True
        return self._values!=d._values

    def keys(self):
        k = set()
        self._keys(self._values, tuple(), k)
        return k

    def _keys(self, d, prefix, k):
        for name in d.keys():
            if name is None:
                k.add(prefix)
            else:
                self._keys(d[name], prefix+(name,), k)

    def intersection(self, otherDict):
        pairs = []
        self._intersect(self._values, otherDict._values, pairs)
        return pairs

    def __collectValues(self, d, values):
        if d.has_key(None):
            values.update(d[None])
        for key in d.keys():
            if key is not None:
                self.__collectValues(d[key], values)

    def _intersect(self, d1, d2, pairs):
        commonNames = set(d1.keys()).intersection(set(d2.keys()))
        
        for name in commonNames:
            if name is not None:
                # take definition and subcomponent references
                if d1[name].has_key(None):
                    locs2 = set()
                    self.__collectValues(d2[name], locs2)
                    for loc1 in d1[name][None]:
                        for loc2 in locs2:
                            pairs.append((loc1,loc2))

                # take reference and subcomponent definitions
                if d2[name].has_key(None):
                    locs1 = set()
                    self.__collectValues(d1[name], locs1)
                    for loc2 in d2[name][None]:
                        for loc1 in locs1:
                            pairs.append((loc1,loc2))

                # recurse
                self._intersect(d1[name], d2[name], pairs)

class LiveVariableDict(Dict):
    pass

class ReachingDefinitionDict(Dict):
    pass

class ReachingDefinitions(object):
    
    def __init__(self, controlFlowModel):
        self.controlFlowModel = controlFlowModel
        self.ins, self.outs = self._analyze()

    def _analyze(self):
        ins = {} # { block: {name: set(cf.ASTLocation)}}
        outs = {} # { block: {name: set(cf.ASTLocation)}}

        # some help functions
        def IN(block):
            if not ins.has_key(block):
                ins[block] = ReachingDefinitionDict()
            return ins[block]

        def OUT(block, createNew=True):
            if not outs.has_key(block):
                if not createNew:
                    return None
                outs[block] = ReachingDefinitionDict()
            return outs[block]

        # start main loop which works until converging of IN/OUT states
        
        working = [] # blocks that have their IN redefined
        working.append(self.controlFlowModel._startBlock)

        while working:
            block = working.pop()
            inDefs = IN(block)
            oldOutDefs = OUT(block, False)
            outDefs = self.transform(inDefs, block)
            changed = (outDefs != oldOutDefs)
            if changed:
                outs[block] = outDefs
                # OUT has changed since the last try
                #  add following basic blocks to the working set as their INs change
                for nextBlock in block.getNextBasicBlocks():
                    if nextBlock==None:
                        # @todo: fix parser (handle "read" statement)
                        # this is only necessary, because fortran parser is not complete
                        #  i.e. there may exist empty block
                        continue 
                    nextInDefs = IN(nextBlock)
                    nextInDefs.update(outDefs)
                    working.append(nextBlock)
        return ins, outs

    def _getDefinitions(self, execution):
        "Return names that are assigned values with ast object as value."
        return {}

    def transform(self, inDefs, block):
        """Transform function for the 'reaching definitions' algorithm.

        @todo: for arrays - add the new, not replace the previous, definition
        """

        if isinstance(block, cf.StartBlock):
            return self.transformWithStartBlock(inDefs, block)
        
        outDefs = ReachingDefinitionDict(inDefs)
        
        for i,execution in enumerate(block.executions):
            defs = self._getDefinitions(execution)
            for assignName,ref in defs.items():
                loc = cf.ASTLocation(block,i,ref)
                outDefs[assignName] = set([loc])

        return outDefs

    def transformWithStartBlock(self, inDefs, block):
        "Return out definitions from start block, which are generated by function arguments."
        outDefs = ReachingDefinitionDict(inDefs)
        return outDefs
