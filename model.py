import torch
import torch.nn as nn
import torchvision.models as models

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class EncoderCNN(nn.Module):
    def __init__(self, embed_size):
        super(EncoderCNN, self).__init__()
        resnet = models.resnet50(pretrained=True)

        for param in resnet.parameters():
            param.requires_grad_(False)
        
        modules = list(resnet.children())[:-1]
        self.resnet = nn.Sequential(*modules)
        self.embed = nn.Linear(resnet.fc.in_features, embed_size)

    def forward(self, images):
        features = self.resnet(images)
        features = features.view(features.size(0), -1)
        features = self.embed(features)
        return features
    

class DecoderRNN(nn.Module):
    def __init__(self, embed_size, hidden_size, vocab_size):
        super().__init__()
        
        self.embed_size = embed_size
        self.hidden_size = hidden_size
        self.vocab_size = vocab_size
        self.num_layers = 1
        
        # embedding layer that turns words into a vector of a specified size
        self.word_embeddings = nn.Embedding(vocab_size, embed_size)

        # the LSTM takes embedded word vectors (of a specified size) as inputs 
        # and outputs hidden states of size hidden_dim
        self.lstm = nn.LSTM(input_size=embed_size,
                            hidden_size=hidden_size,
                            num_layers=self.num_layers,
                            dropout=0,
                            batch_first=True)
        
        self.hidden2vocab = nn.Linear(hidden_size, vocab_size)
    
    def init_hidden(self, batch_size):
        return (torch.zeros((self.num_layers, batch_size, self.hidden_size), device=device), \
                torch.zeros((self.num_layers, batch_size, self.hidden_size), device=device)) 
    
    def forward(self, features, captions):
        ''' Define the feedforward behavior of the model
        
        Note:
            CNN Feature size = Word Embdedding size
        '''
        
        # Discard the <end> word to avoid predicting when <end> is the input of the RNN
        captions = captions[:, :-1]                                    # A. (batch_size, captions_length-1)
        batch_size = features.shape[0]                                 # B. (batch_size, embed_sizeh)
        
        # Create embedded word vectors for each word in the captions
        embeddings  = self.word_embeddings(captions)                   # C. (batch_size, captions_length-1, embed_size)

        # Stack the features and captions
        inputs = torch.cat((features.unsqueeze(1), embeddings), dim=1) # D. (batch_size, caption_length, embed_size)
        hidden = self.init_hidden(batch_size)
        
        lstm_out, hidden = self.lstm(inputs, hidden)               # E. (batch_size, caption length, hidden_size)
#         lstm_out, _ = self.lstm(inputs)
    
        # get the scores for the most likely words
        outputs = self.hidden2vocab(lstm_out);                         # F. (batch_size, caption_length, vocab_size)
        
        return outputs  #[:,:-1,:] # discard the last output of each sample in the batch.

    ## Greedy search 
    def sample(self, inputs):
        " accepts pre-processed image tensor (inputs) and returns predicted sentence (list of tensor ids of length max_len) "
        caption = []
        batch_size = inputs.shape[0]                      # (1, 1, embed_size)  :: batch_size is 1 at inference
        hidden = self.init_hidden(batch_size)
    
        while True:
            lstm_out, hidden = self.lstm(inputs, hidden)  # lstm_out shape : (1, 1, hidden_size)
            outputs = self.hidden2vocab(lstm_out)         # outputs shape : (1, 1, vocab_size)
            outputs = outputs.squeeze(1)                  # outputs shape : (1, vocab_size)
            max_indice = outputs.argmax(dim=1)            # predict the most likely next word, max_indice shape
            
            caption.append(max_indice.item()) # storing the word predicted 
            
            if (max_indice == 1):
                # We predicted the <end> word, so there is no further prediction to do
                break
            
            ## Prepare to embed the last predicted word to be the new input of the lstm
            inputs = self.word_embeddings(max_indice) # inputs shape : (1, embed_size)
            inputs = inputs.unsqueeze(1) # inputs shape : (1, 1, embed_size)
            
        return caption
    
    
    
#     def sample(self, inputs, states=None, max_len=20):
#         " accepts pre-processed image tensor (inputs) and returns predicted sentence (list of tensor ids of length max_len) "
#         caption = []

#         hidden = (torch.randn(self.num_layers, 1, self.hidden_size).to(inputs.device),
#                   torch.randn(self.num_layers, 1, self.hidden_size).to(inputs.device))

#         for i in range(max_len):
#             lstm_out, hidden = self.lstm(inputs, hidden) # batch_size=1, sequence length=1 ->1,1,embedsize
#             outputs = self.hidden2vocab(lstm_out)        # 1,1,vocab_size
#             outputs = outputs.squeeze(1)                 # 1,vocab_size
#             wordid  = outputs.argmax(dim=1)              # 1
#             caption.append(wordid.item())
            
#             # prepare input for next iteration
#             inputs = self.word_embeddings(wordid.unsqueeze(0))  # 1,1->1,1,embed_size
#         return caption