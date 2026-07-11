// Source: data/benchmarks/code2inv/119.c

void loopy_235(int size) {
  
  int i;
  
  int sn;
  
  (sn = 0);
  (i = 1);
  
  while ((i <= size)) {
    {
    (i  = (i + 1));
    (sn  = (sn + 1));
    }

  }
  
if ( (sn != 0) )
{;
//@ assert( (sn == size) );
}

}