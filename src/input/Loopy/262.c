// Source: data/benchmarks/code2inv/23.c

void loopy_262(void) {
  
  int i;
  int j;
  
  (i = 1);
  (j = 20);
  
  while ((j >= i)) {
    {
    (i  = (i + 2));
    (j  = (j - 1));
    }

  }
  
{;
//@ assert( (j == 13) );
}

}